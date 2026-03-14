# CLAUDE.md

## Project
`pdf-up` is a personal CLI that ingests a local PDF into four destinations with one command:

```bash
pdf-up /path/to/file.pdf
```

Targets:
1. Readwise Reader
2. NotebookLM (preconfigured notebook)
3. Zotero
4. Obsidian markdown summary

## Implementation choices
- Language: Python
- Packaging: `pyproject.toml` with console entry point `pdf-up`
- PDF text extraction: PyMuPDF (`fitz`)
- Readwise: Mail.app email import to `add@readwise.io` with PDF attachment
- NotebookLM: local `nlm` CLI with `source add --file --wait`
- Zotero: Web API v3 (collection lookup/create, item creation, PDF attachment upload)
- Summary generation: local `claude --print --permission-mode bypassPermissions`

## Important caveat
Readwise's public Reader API does not expose a true binary-PDF upload endpoint. The current implementation saves the extracted PDF content into Reader as a `pdf` category document using the public API. This is the most reliable available API path unless a private/native upload flow is added later.

## Config
Primary config file:

`~/.config/pdf-up/config.json`

Key fields:
- `readwise_token`
- `notebook_id`
- `obsidian_dir`
- `reader_location`
- `reader_tags`
- `summary_model`
- `zotero_api_key`
- `zotero_user_id`
- `zotero_library_type`
- `zotero_collection`
- `notebooklm_cli`
- `claude_cli`

Environment variable overrides are supported.

## Design goal
Fast, one-command ingestion with concurrent execution and clear per-target success/failure reporting.
