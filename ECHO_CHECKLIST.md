# ECHO Integration Checklist — pdf-up

> Inspected 2026-03-14 by Echo (Integration/QA)

## Status Summary

| Integration  | Installed | API Available | Ready | Priority |
|-------------|-----------|---------------|-------|----------|
| Zotero       | ✅ Running | ✅ Local HTTP + BBT JSON-RPC | 🟢 Go | 1 — best path |
| NotebookLM   | ✅ `nlm` v0.3.16 | ✅ MCP tools in session | 🟢 Go | 2 |
| Obsidian     | ✅ /Applications/Obsidian.app | ⚠️ Filesystem only | 🟡 Partial | 3 |
| Readwise     | ❌ No token/config found | ❌ None | 🔴 Blocked | 4 |

## Repo State

- `/Users/home/projects/pdf-up` is an **empty git repo** (remote: `github.com/amornj/pdf-up`).
- No code, no `package.json`, no tech stack chosen yet.
- All integration work is greenfield.

---

## 1. Zotero — RECOMMENDED FIRST PATH

### What's available
- **Zotero is running** (PID 89497) with local HTTP server on `127.0.0.1:23119`
- **Better BibTeX** plugin installed (v6.7.192) with JSON-RPC endpoint
- **Zotero DB** at `~/Zotero/zotero.sqlite` (has items)
- **Connector API** responds: `GET /connector/ping` → OK
- **BBT JSON-RPC**: `POST /better-bibtex/json-rpc` → functional (minor annotation type error, non-blocking)
- Citation key format: `auth.lower + shorttitle(3,3) + year`

### Recommended implementation
1. **Use BBT JSON-RPC** (`http://127.0.0.1:23119/better-bibtex/json-rpc`) for item search/export
   - Methods: `item.search`, `item.export`, `item.bibliography`
   - Returns BibTeX, CSL-JSON, or formatted citations
2. **Use Zotero Web API** for attachment/PDF access via `http://127.0.0.1:23119/connector/`
3. **pyzotero** is NOT installed — install only if cloud API access needed (requires API key)

### Blockers
- None for local integration (Zotero must be running)

### Test plan
- [ ] `curl POST /better-bibtex/json-rpc` with `item.search` — verify returns items
- [ ] Export a known item as CSL-JSON via BBT
- [ ] Retrieve PDF attachment path for an item
- [ ] Round-trip: search → get metadata → get PDF path

---

## 2. NotebookLM

### What's available
- **`nlm` CLI** v0.3.16 at `~/.local/bin/nlm`
- **MCP tools** available in Claude session (notebook_create, source_add, notebook_query, etc.)
- Auth status: needs verification (run `nlm login` if expired)

### Recommended implementation
- Use **MCP tools directly** from Claude agent context for:
  - Creating notebooks from PDFs (`source_add` with `source_type=file`)
  - Querying notebooks for summaries/Q&A (`notebook_query`)
  - Generating audio overviews (`studio_create`)
- For CLI automation: `nlm` commands in scripts

### Blockers
- Auth token may expire — needs `nlm login` refresh
- No programmatic SDK; limited to MCP tools or CLI wrapper

### Test plan
- [ ] `nlm notebooks list` — verify auth works
- [ ] Create test notebook with a PDF source
- [ ] Query the notebook and verify response quality
- [ ] Test `studio_create` for audio generation

---

## 3. Obsidian

### What's available
- **Obsidian.app** installed at `/Applications/Obsidian.app`
- **Vault** at `~/projects/obsidian/` with content dirs: `Journal/`, `email-digest/`, `youtube/`
- **Plugins installed**: obsidian-git, excalidraw, outliner, tasks, pdf-plus, table-editor, templater
- **No Readwise plugin** — no Readwise sync configured

### Recommended implementation
- **Filesystem integration** — write markdown files directly to vault
  - PDF annotations → markdown notes in vault
  - Zotero metadata → literature note templates via Templater
- **No REST API** — Obsidian has no built-in API; use file writes
- **pdf-plus plugin** already present — may handle PDF viewing/annotation natively

### Blockers
- No Local REST API plugin installed (would need `obsidian-local-rest-api` for HTTP access)
- File-based approach requires knowing vault path and template conventions

### Test plan
- [ ] Write a test markdown file to `~/projects/obsidian/` and verify it appears in Obsidian
- [ ] Check pdf-plus plugin capabilities for PDF annotation export
- [ ] Test Templater-based literature note creation
- [ ] Verify obsidian-git syncs new files

---

## 4. Readwise

### What's available
- **Nothing** — no Readwise token, config, API key, CLI tool, or Obsidian plugin found

### Recommended implementation
- **Skip for now** — requires user to:
  1. Have a Readwise account (paid service)
  2. Generate an API token at readwise.io/access_token
  3. Provide the token for integration
- If token becomes available: Readwise API v2 (`GET/POST https://readwise.io/api/v2/`) for highlights, books, tags

### Blockers
- 🔴 **No API token** — cannot proceed without user providing credentials
- 🔴 **No account confirmation** — unclear if user has Readwise subscription

### Test plan
- [ ] User provides Readwise API token
- [ ] `curl -H "Authorization: Token XXX" https://readwise.io/api/v2/auth/` → verify 204
- [ ] Pull highlights list and verify data shape

---

## Recommendations

### Immediate next steps
1. **Choose tech stack** for pdf-up (suggest: TypeScript/Node or Python)
2. **Start with Zotero** — richest local API, already running, zero config needed
3. **Add NotebookLM** as second integration via MCP tools
4. **Obsidian** as output target (write literature notes to vault)
5. **Readwise** only if user confirms account + provides token

### Architecture suggestion
```
PDF input → pdf-up core
  ├→ Zotero (metadata, citation, PDF storage)
  ├→ NotebookLM (AI analysis, audio overview)
  ├→ Obsidian vault (literature notes, annotations)
  └→ Readwise (highlights sync — if available)
```
