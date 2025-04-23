#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# author: reY2ox
# date: 2025-04-22 13:47
# describe: 
import os
import bs4
import requests
import time
from urllib.parse import urlparse, urlunparse

from config import config
from atlassian import Confluence
from markdownify import MarkdownConverter
from ragflow_sdk import RAGFlow

ATTACHMENT_FOLDER_NAME = "attachments"
DOWNLOAD_CHUNK_SIZE = 4 * 1024 * 1024   # 4MB, since we're single threaded this is safe to raise much higher

class ExportException(Exception):
    pass


class Exporter:
    def __init__(self, url, username, token, out_dir, space):
        self.__out_dir = out_dir
        self.__parsed_url = urlparse(url)
        self.__username = username
        self.__token = token
        self.__confluence = Confluence(url=urlunparse(self.__parsed_url),
                                       username=self.__username,
                                       password=self.__token)
        self.__seen = set()
        self.__no_attach = True
        self.__space = space

    def __sanitize_filename(self, document_name_raw):
        document_name = document_name_raw
        for invalid in ["..", "/"]:
            if invalid in document_name:
                print("Dangerous page title: \"{}\", \"{}\" found, replacing it with \"_\"".format(
                    document_name,
                    invalid))
                document_name = document_name.replace(invalid, "_")
        return document_name

    def __dump_page(self, src_id, parents):
        if src_id in self.__seen:
            # this could theoretically happen if Page IDs are not unique or there is a circle
            raise ExportException("Duplicate Page ID Found!")

        page = self.__confluence.get_page_by_id(src_id, expand="body.storage")
        page_title = page["title"]
        page_id = page["id"]
    
        # see if there are any children
        child_ids = self.__confluence.get_child_id_list(page_id)
    
        content = page["body"]["storage"]["value"]

        # save all files as .html for now, we will convert them later
        extension = ".html"
        document_name = page_title

        # make some rudimentary checks, to prevent trivial errors
        sanitized_filename = self.__sanitize_filename(document_name) + extension
        sanitized_parents = list(map(self.__sanitize_filename, parents))

        page_location = sanitized_parents + [sanitized_filename]
        page_filename = os.path.join(self.__out_dir, *page_location)

        page_output_dir = os.path.dirname(page_filename)
        os.makedirs(page_output_dir, exist_ok=True)
        print("Saving to {}".format(" / ".join(page_location)))
        with open(page_filename, "w", encoding="utf-8") as f:
            f.write(content)

        # fetch attachments unless disabled
        if not self.__no_attach:
            ret = self.__confluence.get_attachments_from_content(page_id, start=0, limit=500, expand=None,
                                                                 filename=None, media_type=None)
            for i in ret["results"]:
                att_title = i["title"]
                download = i["_links"]["download"]

                att_url = urlunparse(
                    (self.__parsed_url[0], self.__parsed_url[1], "/wiki/" + download.lstrip("/"), None, None, None)
                )
                att_sanitized_name = self.__sanitize_filename(att_title)
                att_filename = os.path.join(page_output_dir, ATTACHMENT_FOLDER_NAME, att_sanitized_name)

                att_dirname = os.path.dirname(att_filename)
                os.makedirs(att_dirname, exist_ok=True)

                print("Saving attachment {} to {}".format(att_title, page_location))

                print("Using url: {}".format(att_url))
                r = requests.get(att_url, auth=(self.__username, self.__token), stream=True)
                if 400 <= r.status_code:
                    if r.status_code == 404:
                        print("Attachment {} not found (404)!".format(att_url))
                        continue

                    # this is a real error, raise it
                    r.raise_for_status()

                with open(att_filename, "wb") as f:
                    for buf in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        f.write(buf)

        self.__seen.add(page_id)
    
        # recurse to process child nodes
        for child_id in child_ids:
            self.__dump_page(child_id, parents=sanitized_parents + [page_title])

    def __dump_space(self, space):
        space_key = space["key"]
        print("Processing space", space_key)
        if space.get("homepage") is None:
            print("Skipping space: {}, no homepage found!".format(space_key))
            print("In order for this tool to work there has to be a root page!")
            raise ExportException("No homepage found")
        else:
            # homepage found, recurse from there
            homepage_id = space["homepage"]["id"]
            self.__dump_page(homepage_id, parents=[space_key])

    
    def dump(self):
        ret = self.__confluence.get_all_spaces(start=0, limit=500, expand='description.plain,homepage')
        if ret['size'] == 0:
            print("No spaces found in confluence. Please check credentials")
        for space in ret["results"]:
            if self.__space is None or space["key"] == self.__space:
                self.__dump_space(space)

class Converter:
    def __init__(self, out_dir):
        self.__out_dir = out_dir

    def recurse_findfiles(self, path):
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                yield from self.recurse_findfiles(entry.path)
            elif entry.is_file(follow_symlinks=False):
                yield entry
            else:
                raise NotImplemented()

    def __convert_atlassian_html(self, soup):
        for image in soup.find_all("ac:image"):
            url = None
            for child in image.children:
                url = child.get("ri:filename", None)
                break

            if url is None:
                # no url found for ac:image
                continue

            # construct new, actually valid HTML tag
            srcurl = os.path.join(ATTACHMENT_FOLDER_NAME, url)
            imgtag = soup.new_tag("img", attrs={"src": srcurl, "alt": srcurl})

            # insert a linebreak after the original "ac:image" tag, then replace with an actual img tag
            image.insert_after(soup.new_tag("br"))
            image.replace_with(imgtag)
        return soup

    def convert(self):
        for entry in self.recurse_findfiles(self.__out_dir):
            path = entry.path

            if not path.endswith(".html"):
                continue

            print("Converting {}".format(path))
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()

            soup_raw = bs4.BeautifulSoup(data, 'html.parser')
            soup = self.__convert_atlassian_html(soup_raw)

            md = MarkdownConverter().convert_soup(soup)
            newname = os.path.splitext(path)[0]
            with open(newname + ".txt", "w", encoding="utf-8") as f:
                f.write(md)
            os.remove(path) #删除html文件


class UpToRAG():
    def __init__(self, out_dir):
        self.__out_dir = out_dir
        self.__rag_object = RAGFlow(base_url=config.RAGFLOW_URL, api_key=config.RAGFLOW_API)
    
    def recurse_findfiles(self, path):
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                yield from self.recurse_findfiles(entry.path)
            elif entry.is_file(follow_symlinks=False):
                yield entry
            else:
                raise NotImplemented()
    
    def upload(self):
        for entry in self.recurse_findfiles(self.__out_dir):
            path = entry.path
            name = os.path.basename(path)
            if not path.endswith(".txt") or "模版" in name:
                continue

            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            
            if not data.strip():
                print("File content is empty, skipping upload")
                continue
            
            # Temporarily replace delimiters
            if "⸻" in data:
                pass
            else:
                data = data.replace("---", "⸻")

            dataset = self.__rag_object.list_datasets(name=config.RAGFLOW_DATASET_NAME)
            if not dataset:
                print(f"Dataset '{config.RAGFLOW_DATASET_NAME}' not found, skipping upload for <{name}>")
                continue

            # Check if the file exists, delete it if it does
            if dataset[0].list_documents(keywords=name):
                print(f"<{name}> file already exists, deleting")
                dataset[0].delete_documents([dataset[0].list_documents(keywords=name)[0].id])

            # Upload the file
            dataset[0].upload_documents([{"display_name": name, "blob": data}])
            # Parse the document
            dataset[0].async_parse_documents([dataset[0].list_documents(keywords=name)[0].id])
            # Check parsing status
            while True:
                progress = dataset[0].list_documents(keywords=name)[0].progress
                try:
                    progress = float(progress)
                except (ValueError, TypeError):
                    print(f"<{name}> progress value is invalid: {progress}")
                    break

                if progress == 1.0:
                    print(f"<{name}> document parsing completed")
                    break
                elif 0 < progress < 1:
                    print("Document parsing in progress..., current progress: {:.2f}%".format(progress * 100))
                elif progress == 0.0:
                    print(f"<{name}> parsing not started")
                    break
                elif progress == -1.0:
                    print(f"<{name}> parsing failed")
                    break
                time.sleep(5)
            

def main():
    dumper = Exporter(url=config.CONFLUENCE_URL, username=config.USERNAME, token=config.PASSWORD, out_dir="./download",space=config.SPACE)
    dumper.dump()
    converter = Converter(out_dir="./download")
    converter.convert()
    
    uploader = UpToRAG(out_dir="./download")
    uploader.upload()

if __name__ == "__main__":
    main()