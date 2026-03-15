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
- Readwise: Mail.app email import to the user's Reader library forwarding address with PDF attachment
- NotebookLM: local `nlm` CLI with `source add --file --wait`
- Zotero: Web API v3, metadata-only item creation in target collection
- Summary generation: local `claude --print --permission-mode bypassPermissions`

## Important caveat
Reader is the real PDF storage destination. Zotero is intentionally metadata-only to avoid consuming Zotero free-tier file storage.

## Config
Primary config file:

`~/.config/pdf-up/config.json`

Key fields:
- `reader_email_account`
- `reader_forwarding_email`
- `notebook_id`
- `obsidian_dir`
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
