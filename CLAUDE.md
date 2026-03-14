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
- Zotero: Web API v3 (collection lookup/create, parent item creation, PDF attachment upload)
- Summary generation: local `claude --print --permission-mode bypassPermissions`

## Important caveat
Reader uses Mail.app email import of the actual PDF attachment. Zotero uses the Web API and requires a valid API key/user ID with file-write permissions.

## Config
Primary config file:

`~/.config/pdf-up/config.json`

Key fields:
- `readwise_token` (optional if using email import only)
- `reader_email_account`
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

## Interactive mode
By default, `pdf-up` shows current settings (Obsidian folder, NotebookLM notebook by name, Zotero collection) and asks for confirmation before executing. Users can edit any setting inline. After confirmation, interactive choices are persisted back to `~/.config/pdf-up/config.json` so the next run defaults to the last-used values. The `--yes` / `--non-interactive` flag bypasses all prompts. The `--notebook <name>` flag resolves a notebook name to its ID via the `nlm` CLI; if multiple notebooks match, a numbered picker is shown.

Key modules:
- `prompts.py` — interactive prompt loop with confirm
- `notebooks.py` — NotebookLM name↔ID resolution via `nlm notebook list`

## Design goal
Fast, one-command ingestion with concurrent execution and clear per-target success/failure reporting.
