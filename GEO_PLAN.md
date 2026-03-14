# pdf-up — Implementation Brief

> CLI tool that ingests a local PDF into four destinations concurrently:
> Readwise Reader, NotebookLM, Zotero, and Obsidian (markdown summary).

---

## 1. CLI UX

```
pdf-up <pdf-path> [options]

Options:
  --title, -t <string>       Override document title (default: PDF filename stem)
  --tags <tag1,tag2>          Tags for Readwise & Zotero
  --collection, -c <string>  Zotero collection key
  --notebook, -n <string>    NotebookLM notebook ID or nlm alias (overrides config default)
  --obsidian-folder <path>   Obsidian vault subfolder (overrides config default)
  --dry-run                  Validate config and print what would happen
  --json                     Output structured JSON instead of human-readable text
  --verbose, -v              Show per-task progress
  --version                  Print version
  --help, -h                 Show help
```

**Minimum invocation:** `pdf-up paper.pdf`
(all destinations use config defaults; title derived from filename)

### Interactive feedback

```
$ pdf-up paper.pdf
◐ Uploading to 4 destinations...
  ✓ Readwise Reader  — https://read.readwise.io/new/read/abc123
  ✓ NotebookLM       — source added to "DLP2026"
  ✗ Zotero           — 403 Forbidden (check API key permissions)
  ✓ Obsidian         — ~/vault/Inbox/paper.md

3/4 succeeded (exit 2)
```

---

## 2. Architecture

```
pdf-up (CLI entry)
├── config.load()          — merge env → config file → CLI flags
├── validate(pdf_path)     — file exists, is PDF, ≤200 MB
└── concurrent.futures / asyncio.gather()
    ├── readwise.upload()
    ├── notebooklm.upload()
    ├── zotero.upload()
    └── obsidian.summarize()
```

**Language:** Python 3.11+ (best library support for all four APIs).
**Packaging:** Single `pyproject.toml`, installable via `pipx install .`

### Key dependencies

| Dep | Purpose |
|-----|---------|
| `httpx` | Async HTTP for Readwise & Zotero |
| `pyzotero` | Zotero upload handshake (handles 5-step auth dance) |
| `pymupdf` (fitz) | PDF text extraction for Obsidian summary |
| `anthropic` | Claude API for summarisation (or local fallback) |
| `click` | CLI framework |
| `rich` | Terminal spinners, colours, tables |

---

## 3. Per-Destination Integration

### 3a. Readwise Reader

- **Endpoint:** `POST https://readwise.io/api/v3/save/`
- **Auth:** `Authorization: Token <READWISE_TOKEN>`
- **Problem:** API does not accept raw PDF binary. Only URLs or HTML.
- **Solution (pick one at config time):**
  1. **`readwise_method = "email"`** — send PDF as attachment to `add@readwise.io` via SMTP (simplest, no hosting needed). Requires `SMTP_*` env vars or use the user's local `msmtp`/`sendmail`.
  2. **`readwise_method = "url"`** — upload PDF to a temp public URL first (e.g., `transfer.sh`, S3 presigned URL, or a local ngrok tunnel), then POST the URL with `category: "pdf"`.
  3. **`readwise_method = "temphost"`** — spin up a 60-second local HTTP server, use ngrok/cloudflared tunnel, POST URL, tear down.

**Recommended default:** `email` — zero infrastructure, works reliably.

### 3b. NotebookLM

- **Method:** Shell out to `nlm source add <notebook_id> --file <pdf_path> --wait`
  - `nlm` is already installed at `~/.local/bin/nlm`
  - Alternatively, call MCP `source_add` tool if running inside an MCP-aware context
- **Config:** `NOTEBOOKLM_NOTEBOOK_ID` or `nlm` alias
- **Limits:** ≤200 MB, ≤500k words, ≤50 sources/notebook, no encrypted PDFs

### 3c. Zotero

- **Library:** `pyzotero` — handles the 5-step upload handshake
- **Flow:**
  1. Create parent item (`itemType: "document"`, title, tags)
  2. `zot.attachment_simple([pdf_path], parent_key)` — handles auth, upload, register
- **Config:** `ZOTERO_API_KEY`, `ZOTERO_USER_ID`, optional `ZOTERO_COLLECTION`
- **Limit:** 300 MB free storage; warn if approaching quota

### 3d. Obsidian (Markdown Summary)

- **Flow:**
  1. Extract text from PDF via `pymupdf`
  2. Send to Claude API: `"Summarize this academic paper into structured markdown with: title, authors, abstract, key findings, methodology, limitations, and references."`
  3. Write output to `<obsidian_vault>/<folder>/<title>.md` with YAML frontmatter
- **Frontmatter:**
  ```yaml
  ---
  title: "Paper Title"
  source: "/path/to/original.pdf"
  date_added: 2026-03-14
  tags: [pdf-up, research]
  ---
  ```
- **Config:** `OBSIDIAN_VAULT_PATH`, `OBSIDIAN_FOLDER` (default: `Inbox`)
- **LLM fallback:** If no `ANTHROPIC_API_KEY`, do extractive summary (first 500 words + headings)

---

## 4. Configuration

### 4a. Config file: `~/.config/pdf-up/config.toml`

```toml
[readwise]
method = "email"         # "email" | "url" | "temphost"
# token set via env var

[notebooklm]
notebook_id = "d06ca6ae-e7f2-451b-ba7a-d40eb1138d0f"
# or: alias = "dlp"

[zotero]
# user_id and api_key set via env vars
collection = ""          # optional default collection key

[obsidian]
vault_path = "/Users/home/obsidian-vault"
folder = "Inbox"

[summary]
model = "claude-sonnet-4-6"  # or "none" for extractive fallback
```

### 4b. Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `READWISE_TOKEN` | Yes* | From readwise.io/access_token |
| `NOTEBOOKLM_NOTEBOOK_ID` | Yes* | Target notebook UUID (or set in config) |
| `ZOTERO_API_KEY` | Yes* | From zotero.org/settings/keys |
| `ZOTERO_USER_ID` | Yes* | Numeric user ID from Zotero settings |
| `ANTHROPIC_API_KEY` | No | For Claude-powered summaries; extractive fallback without it |
| `OBSIDIAN_VAULT_PATH` | Yes* | Absolute path to Obsidian vault root |

*Required only if that destination is enabled. Each destination can be disabled individually.

### 4c. Precedence

`CLI flags > env vars > config.toml > defaults`

---

## 5. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| PDF not found / not a PDF | Exit 1 immediately, don't attempt any uploads |
| Missing config for a destination | Skip that destination, warn, continue others |
| Single destination fails | Log error, continue others, report in summary |
| All destinations fail | Exit 1 |
| Network timeout | 30s per destination, configurable |
| PDF too large (>200 MB) | Warn for NLM limit, attempt others |
| Auth failure (401/403) | Clear error message with link to re-auth |
| Ctrl+C | Cancel in-flight requests, report partial results |

**Retry policy:** 1 automatic retry with exponential backoff for 5xx / network errors. No retry for 4xx.

---

## 6. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All destinations succeeded |
| 1 | Fatal error (bad input, no valid config, all destinations failed) |
| 2 | Partial success (≥1 destination failed, ≥1 succeeded) |

---

## 7. Output Format

### Human (default)

```
pdf-up v0.1.0 — paper.pdf (2.3 MB)

  ✓ Readwise Reader  sent via email to add@readwise.io
  ✓ NotebookLM       source added to "DLP2026" (processing...)
  ✓ Zotero           item ABCD1234 in My Library
  ✓ Obsidian         ~/vault/Inbox/paper.md

4/4 succeeded
```

### JSON (`--json`)

```json
{
  "file": "paper.pdf",
  "size_bytes": 2412000,
  "results": {
    "readwise": {"status": "ok", "detail": "emailed to add@readwise.io"},
    "notebooklm": {"status": "ok", "detail": "source added", "notebook": "DLP2026"},
    "zotero": {"status": "ok", "detail": "item ABCD1234", "key": "ABCD1234"},
    "obsidian": {"status": "ok", "detail": "/Users/home/vault/Inbox/paper.md"}
  },
  "succeeded": 4,
  "failed": 0,
  "exit_code": 0
}
```

---

## 8. File Structure

```
pdf-up/
├── pyproject.toml
├── src/
│   └── pdf_up/
│       ├── __init__.py
│       ├── cli.py              # click entry point
│       ├── config.py           # toml + env + flag merging
│       ├── runner.py           # concurrent dispatch
│       ├── destinations/
│       │   ├── __init__.py
│       │   ├── readwise.py
│       │   ├── notebooklm.py
│       │   ├── zotero.py
│       │   └── obsidian.py
│       └── pdf_utils.py        # text extraction, validation
└── tests/
    ├── test_config.py
    ├── test_runner.py
    └── test_destinations/
```

---

## 9. Open Questions

1. **Readwise upload method** — email is simplest but has no confirmation callback. URL method gives a Reader URL back but needs hosting. Decide based on user preference.
2. **Zotero parent item type** — should we attempt metadata extraction (DOI lookup via CrossRef) to create a proper bibliographic entry, or just use generic "document" type?
3. **Summary LLM** — Claude Sonnet 4.6 is fast/cheap. Should we support local models (Ollama) as a fallback for offline use?
4. **Batch mode** — `pdf-up *.pdf` or `pdf-up --dir ./papers/` for bulk import? Defer to v0.2.
