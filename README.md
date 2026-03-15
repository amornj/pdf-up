# pdf-up

`pdf-up` ingests a local PDF into your research workflow with one command.

```bash
pdf-up /path/to/paper.pdf
```

It runs four tasks concurrently:

1. **Readwise Reader** email import of the actual PDF via Mail.app
2. **NotebookLM** source upload to a preconfigured notebook
3. **Zotero** Web API metadata-only item creation
4. **Obsidian** markdown summary generation

## What it does

Given a local PDF path, `pdf-up`:
- extracts text from the PDF
- sends the original PDF as an email attachment to your Reader **library forwarding address** using Mail.app
- uploads the original file to NotebookLM using the local `nlm` CLI
- creates a **metadata-only** Zotero item in the requested collection (no PDF attachment upload)
- generates a markdown summary in your configured Obsidian folder using Claude CLI

## Install

From the repo root:

```bash
python3 -m pip install -e .
```

If the script lands outside your shell PATH, add this to `~/.zshrc`:

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH"
```

Then reload:

```bash
source ~/.zshrc
```

## Configuration

Create starter config:

```bash
pdf-up --init-config
```

This writes:

```bash
~/.config/pdf-up/config.json
```

Example config:

```json
{
  "readwise_token": "OPTIONAL_IF_USING_EMAIL_IMPORT",
  "reader_email_account": "Google",
  "reader_forwarding_email": "amornj@library.readwise.io",
  "notebook_id": "YOUR_NOTEBOOKLM_NOTEBOOK_ID",
  "obsidian_dir": "/Users/home/projects/obsidian/journal",
  "reader_location": "new",
  "reader_tags": ["pdf-up"],
  "summary_model": "sonnet",
  "zotero_api_key": "YOUR_ZOTERO_API_KEY",
  "zotero_user_id": "7734498",
  "zotero_library_type": "user",
  "zotero_collection": "amyloidosis",
  "notebooklm_cli": "/Users/home/.local/bin/nlm",
  "claude_cli": "/Users/home/.local/bin/claude"
}
```

## Environment overrides

These override config file values when set:

- `PDF_UP_READWISE_TOKEN`
- `PDF_UP_READER_EMAIL_ACCOUNT`
- `PDF_UP_READER_FORWARDING_EMAIL`
- `PDF_UP_NOTEBOOK_ID`
- `PDF_UP_OBSIDIAN_DIR`
- `PDF_UP_READER_LOCATION`
- `PDF_UP_READER_TAGS`
- `PDF_UP_SUMMARY_MODEL`
- `PDF_UP_ZOTERO_API_KEY`
- `PDF_UP_ZOTERO_USER_ID`
- `PDF_UP_ZOTERO_LIBRARY_TYPE`
- `PDF_UP_ZOTERO_COLLECTION`
- `PDF_UP_NLM_CLI`
- `PDF_UP_CLAUDE_CLI`

## Usage

```bash
pdf-up ~/Downloads/paper.pdf
```

By default, `pdf-up` runs in **interactive mode**: it shows current settings (Obsidian folder, NotebookLM notebook name, Zotero collection), lets you edit them inline, and asks for confirmation before executing.

To skip the interactive prompts and run immediately with current/default settings:

```bash
pdf-up ~/Downloads/paper.pdf --yes
# or
pdf-up ~/Downloads/paper.pdf --non-interactive
```

Override NotebookLM notebook by name (resolved to ID automatically):

```bash
pdf-up ~/Downloads/paper.pdf --notebook amyloidosis
```

Other overrides:

```bash
pdf-up ~/Downloads/paper.pdf \
  --notebook-id YOUR_NOTEBOOK_ID \
  --obsidian-dir /Users/home/projects/obsidian/journal/inbox \
  --summary-model sonnet \
  --zotero-collection amyloidosis \
  --reader-email-account Google
```

## Output

Example:

```text
[OK] readwise: Sent PDF attachment to amornj@library.readwise.io via Mail account Google
[OK] notebooklm: Uploaded to NotebookLM ...
[OK] zotero: Created metadata-only Zotero item in collection "amyloidosis" (...)
[OK] obsidian: Wrote markdown summary: ...
```

Exit code:
- `0` if all 4 tasks succeed
- `1` if any task fails

## Notes / caveats

### Readwise Reader
`pdf-up` uses **Reader email import** for actual PDFs by sending the file as an attachment to your **library forwarding address** through Mail.app.

Default forwarding address:

```text
amornj@library.readwise.io
```

### NotebookLM
This tool expects the local `nlm` CLI to already be authenticated.

### Zotero
Zotero integration uses the [Zotero Web API v3](https://www.zotero.org/support/dev/web_api/v3/start).

Current Zotero behavior is intentionally **metadata-only**:
- looks up or creates the target collection
- creates a top-level bibliographic item
- does **not** upload the PDF attachment

This avoids consuming Zotero file storage, while the real PDF lives in Reader and NotebookLM.

### Obsidian summaries
Summary generation uses the local Claude CLI. Very large PDFs are summarized from extracted text content rather than embedded page images.
