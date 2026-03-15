from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz


class PdfUpError(Exception):
    pass


@dataclass
class PdfDocument:
    path: Path
    title: str
    text: str
    excerpt: str
    content_hash: str


@dataclass
class TaskResult:
    name: str
    ok: bool
    details: str


def extract_pdf(path: Path) -> PdfDocument:
    if not path.exists():
        raise PdfUpError(f'PDF not found: {path}')
    if path.suffix.lower() != '.pdf':
        raise PdfUpError(f'Expected a .pdf file: {path}')

    doc = fitz.open(path)
    texts: list[str] = []
    meta_title = (doc.metadata or {}).get('title') or ''
    for page in doc:
        texts.append(page.get_text('text'))
    text = '\n\n'.join(t.strip() for t in texts if t.strip())
    title = meta_title.strip() or path.stem.replace('_', ' ').replace('-', ' ').strip()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    excerpt = text[:60000]
    return PdfDocument(path=path, title=title, text=text, excerpt=excerpt, content_hash=content_hash)


def upload_to_readwise(pdf: PdfDocument, config: dict[str, Any]) -> TaskResult:
    account = config.get('reader_email_account', 'Google')
    forwarding = config.get('reader_forwarding_email', 'amornj@library.readwise.io')
    safe_subject = pdf.title.replace('"', "'")
    safe_body = f'Imported by pdf-up from local file: {pdf.path}'.replace('"', "'")
    safe_path = str(pdf.path).replace('"', '\\"')
    script = f'''
    tell application "Mail"
      set targetAccount to first account whose name is "{account}"
      set newMessage to make new outgoing message with properties {{subject:"{safe_subject}", content:"{safe_body}" & return & return, visible:false}}
      tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{forwarding}"}}
        make new attachment with properties {{file name:POSIX file "{safe_path}"}} at after the last paragraph
        send
      end tell
    end tell
    '''
    proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise PdfUpError(f'Reader email import failed: {(proc.stderr or proc.stdout).strip()[:400]}')
    return TaskResult('readwise', True, f'Sent PDF attachment to {forwarding} via Mail account {account}')


def upload_to_notebooklm(pdf: PdfDocument, config: dict[str, Any]) -> TaskResult:
    notebook_id = config.get('notebook_id')
    if not notebook_id or notebook_id == 'YOUR_NOTEBOOKLM_NOTEBOOK_ID':
        return TaskResult('notebooklm', False, 'Missing notebook_id in config/env')
    nlm = config.get('notebooklm_cli') or 'nlm'
    if not shutil.which(nlm) and not Path(nlm).exists():
        return TaskResult('notebooklm', False, f'NotebookLM CLI not found: {nlm}')

    cmd = [nlm, 'source', 'add', notebook_id, '--file', str(pdf.path), '--wait']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise PdfUpError(f'NotebookLM upload failed: {(proc.stderr or proc.stdout).strip()[:400]}')
    return TaskResult('notebooklm', True, (proc.stdout or 'Uploaded to NotebookLM').strip()[:300])


def summarize_to_obsidian(pdf: PdfDocument, config: dict[str, Any]) -> TaskResult:
    obsidian_dir = Path(config.get('obsidian_dir', '.')).expanduser()
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    claude = config.get('claude_cli') or 'claude'
    if not shutil.which(claude) and not Path(claude).exists():
        return TaskResult('obsidian', False, f'Claude CLI not found: {claude}')

    prompt = f'''You are summarizing a PDF for an Obsidian note.
Return markdown only.

Create:
- Title
- Citation (if inferable; otherwise use filename)
- Summary (3-5 paragraphs)
- Key points (bullets)
- Clinical / practical implications (bullets)
- 5 take-home messages

Filename: {pdf.path.name}
Path: {pdf.path}

PDF TEXT:
{pdf.excerpt}
'''
    proc = subprocess.run(
        [claude, '--permission-mode', 'bypassPermissions', '--print', '--model', config.get('summary_model', 'sonnet'), prompt],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(pdf.path.parent if pdf.path.parent.exists() else Path.home()),
    )
    if proc.returncode != 0:
        raise PdfUpError(f'Summary generation failed: {(proc.stderr or proc.stdout).strip()[:400]}')
    slug = pdf.path.stem.lower().replace(' ', '-').replace('_', '-')
    out = obsidian_dir / f'{slug}.md'
    header = f'# {pdf.title}\n\n> Source PDF: `{pdf.path}`\n\n'
    out.write_text(header + proc.stdout.strip() + '\n')
    return TaskResult('obsidian', True, f'Wrote markdown summary: {out}')


def format_results(results: list[TaskResult]) -> str:
    lines = []
    for r in results:
        status = 'OK' if r.ok else 'FAIL'
        lines.append(f'[{status}] {r.name}: {r.details}')
    return '\n'.join(lines)
