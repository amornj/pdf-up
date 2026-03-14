# pdf-up

`pdf-up` ingests a local PDF into your research workflow with one command.

```bash
pdf-up /path/to/paper.pdf
```

It runs four tasks concurrently:

1. **Readwise Reader** import
2. **NotebookLM** source upload to a preconfigured notebook
3. **Zotero** import trigger
4. **Obsidian** markdown summary generation

## What it does

Given a local PDF path, `pdf-up`:
- extracts text from the PDF
- sends the document into Reader using the public Reader API
- uploads the original file to NotebookLM using the local `nlm` CLI
- opens the file in Zotero for import
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
  "readwise_token": "YOUR_READWISE_TOKEN",
  "notebook_id": "YOUR_NOTEBOOKLM_NOTEBOOK_ID",
  "obsidian_dir": "/Users/home/projects/obsidian/journal",
  "reader_location": "new",
  "reader_tags": ["pdf-up"],
  "summary_model": "sonnet",
  "zotero_app": "Zotero",
  "notebooklm_cli": "/Users/home/.local/bin/nlm",
  "claude_cli": "/Users/home/.local/bin/claude"
}
```

## Environment overrides

These override config file values when set:

- `PDF_UP_READWISE_TOKEN`
- `PDF_UP_NOTEBOOK_ID`
- `PDF_UP_OBSIDIAN_DIR`
- `PDF_UP_READER_LOCATION`
- `PDF_UP_READER_TAGS`
- `PDF_UP_SUMMARY_MODEL`
- `PDF_UP_ZOTERO_APP`
- `PDF_UP_NLM_CLI`
- `PDF_UP_CLAUDE_CLI`

## Usage

```bash
pdf-up ~/Downloads/paper.pdf
```

Optional overrides:

```bash
pdf-up ~/Downloads/paper.pdf \
  --notebook-id YOUR_NOTEBOOK_ID \
  --obsidian-dir /Users/home/projects/obsidian/journal/inbox \
  --summary-model sonnet
```

## Commands

Print config path:

```bash
pdf-up --config-path
```

Initialize config:

```bash
pdf-up --init-config
```

## Output

The CLI prints one status line per target, for example:

```text
[OK] readwise: Saved to Reader: ...
[OK] notebooklm: Uploaded to NotebookLM ...
[OK] zotero: Triggered import in Zotero via open -a
[OK] obsidian: Wrote markdown summary: ...
```

Exit code:
- `0` if all 4 tasks succeed
- `1` if any task fails

## Notes / caveats

### Readwise Reader
The public Reader API does **not** expose a true raw-binary PDF upload endpoint. `pdf-up` uses the public API to create a Reader document in `pdf` category from extracted content and metadata. This is the most reliable supported API path available today.

### NotebookLM
This tool expects the local `nlm` CLI to already be authenticated.

### Zotero
Current integration uses:

```bash
open -a Zotero /path/to/file.pdf
```

So Zotero must be installed locally.

### Obsidian summaries
Summary generation uses the local Claude CLI. Very large PDFs are summarized from extracted text content rather than embedded page images.
