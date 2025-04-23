# Confluence to RAGFlow

This project is a tool for exporting Confluence pages, converting them to Markdown, and uploading them to a RAGFlow knowledge base. It is designed to streamline the process of migrating and managing Confluence content in RAGFlow.

## Features

- Export Confluence pages and attachments.
- Convert Confluence HTML content to Markdown format.
- Upload converted content to a RAGFlow knowledge base.
- Automatically handle document parsing and status monitoring.

## Requirements

- **Python 3.10 or higher** (required for `ragflow_sdk`)
- Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo/confluence-to-ragflow.git
   cd confluence-to-ragflow
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
3. Configure the project by editing the config.py file with your Confluence and RAGFlow credentials.

## Usage
Run the main script to export, convert, and upload Confluence content: 

```bash
python main.py
```

## Configuration
Update the config.py file with the following details:

**CONFLUENCE_URL**: The base URL of your Confluence instance.
**USERNAME**: Your Confluence username.
**PASSWORD**: Your Confluence API token.
**SPACE**: The Confluence space key to export.
**RAGFLOW_URL**: The base URL of your RAGFlow instance.
**RAGFLOW_API**: Your RAGFlow API key.
**RAGFLOW_DATASET_NAME**: The name of the RAGFlow dataset to upload content to.

## Acknowledgments

This project is based on and modified from **[confluence-markdown-exporter](https://github.com/gergelykalman/confluence-markdown-exporter)**. We extend our gratitude to the original author for their work.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
