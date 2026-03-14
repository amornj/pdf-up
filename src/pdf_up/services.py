from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
import requests


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
    safe_subject = pdf.title.replace('"', "'")
    safe_body = f'Imported by pdf-up from local file: {pdf.path}'.replace('"', "'")
    safe_path = str(pdf.path).replace('"', '\\"')
    script = f'''
    tell application "Mail"
      set targetAccount to first account whose name is "{account}"
      set newMessage to make new outgoing message with properties {{subject:"{safe_subject}", content:"{safe_body}" & return & return, visible:false}}
      tell newMessage
        make new to recipient at end of to recipients with properties {{address:"add@readwise.io"}}
        make new attachment with properties {{file name:POSIX file "{safe_path}"}} at after the last paragraph
        send
      end tell
    end tell
    '''
    proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise PdfUpError(f'Reader email import failed: {(proc.stderr or proc.stdout).strip()[:400]}')
    return TaskResult('readwise', True, f'Sent PDF attachment to add@readwise.io via Mail account {account}')


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


def _zotero_headers(api_key: str) -> dict[str, str]:
    return {
        'Zotero-API-Key': api_key,
        'Content-Type': 'application/json',
        'Zotero-API-Version': '3',
    }


def _zotero_base_url(config: dict[str, Any]) -> str:
    lib_type = config.get('zotero_library_type', 'user')
    user_id = config['zotero_user_id']
    prefix = 'users' if lib_type == 'user' else 'groups'
    return f'https://api.zotero.org/{prefix}/{user_id}'


def _zotero_find_or_create_collection(base_url: str, headers: dict[str, str], name: str) -> str | None:
    """Find a collection by name, or create it. Returns collection key or None if name is empty."""
    if not name:
        return None
    resp = requests.get(f'{base_url}/collections', headers=headers, params={'q': name}, timeout=30)
    resp.raise_for_status()
    for col in resp.json():
        if col['data']['name'].lower() == name.lower():
            return col['key']
    # Create collection
    payload = [{'name': name}]
    resp = requests.post(f'{base_url}/collections', headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    created = result.get('successful', {})
    if created:
        return next(iter(created.values()))['key']
    raise PdfUpError(f'Failed to create Zotero collection "{name}": {json.dumps(result.get("failed", {}))}')


def _zotero_create_parent_item(base_url: str, headers: dict[str, str], pdf: PdfDocument, collection_key: str | None) -> str:
    """Create a top-level document item. Returns item key."""
    item: dict[str, Any] = {
        'itemType': 'document',
        'title': pdf.title,
    }
    if collection_key:
        item['collections'] = [collection_key]
    resp = requests.post(f'{base_url}/items', headers=headers, json=[item], timeout=30)
    resp.raise_for_status()
    result = resp.json()
    created = result.get('successful', {})
    if created:
        return next(iter(created.values()))['key']
    raise PdfUpError(f'Failed to create Zotero item: {json.dumps(result.get("failed", {}))}')


def _zotero_upload_attachment(base_url: str, api_key: str, parent_key: str, pdf: PdfDocument) -> str:
    """Create an imported-file attachment and upload the PDF binary. Returns attachment key."""
    headers = _zotero_headers(api_key)
    # Step 1: create the attachment item linked to parent
    attachment = {
        'itemType': 'attachment',
        'parentItem': parent_key,
        'linkMode': 'imported_file',
        'title': pdf.path.name,
        'contentType': 'application/pdf',
        'filename': pdf.path.name,
    }
    resp = requests.post(f'{base_url}/items', headers=headers, json=[attachment], timeout=30)
    resp.raise_for_status()
    result = resp.json()
    created = result.get('successful', {})
    if not created:
        raise PdfUpError(f'Failed to create attachment item: {json.dumps(result.get("failed", {}))}')
    att_key = next(iter(created.values()))['key']

    # Step 2: get upload authorization
    file_bytes = pdf.path.read_bytes()
    file_hash = hashlib.md5(file_bytes).hexdigest()  # noqa: S324
    file_size = len(file_bytes)
    auth_headers = {
        'Zotero-API-Key': api_key,
        'Zotero-API-Version': '3',
        'Content-Type': 'application/x-www-form-urlencoded',
        'If-None-Match': '*',
    }
    auth_body = f'md5={file_hash}&filename={pdf.path.name}&filesize={file_size}&mtime={int(pdf.path.stat().st_mtime * 1000)}'
    resp = requests.post(f'{base_url}/items/{att_key}/file', headers=auth_headers, data=auth_body, timeout=30)
    resp.raise_for_status()
    auth = resp.json()

    if auth.get('exists'):
        return att_key  # file already exists in Zotero storage

    # Step 3: upload to the provided URL
    upload_url = auth['url']
    upload_headers = {h['name']: h['value'] for h in auth.get('headers', {})} if isinstance(auth.get('headers'), list) else {}
    prefix = (auth.get('prefix') or '').encode()
    suffix = (auth.get('suffix') or '').encode()
    content_type = auth.get('contentType', 'application/pdf')
    upload_body = prefix + file_bytes + suffix
    resp = requests.post(upload_url, headers={**upload_headers, 'Content-Type': content_type}, data=upload_body, timeout=120)
    resp.raise_for_status()

    # Step 4: register the upload
    reg_headers = {
        'Zotero-API-Key': api_key,
        'Zotero-API-Version': '3',
        'Content-Type': 'application/x-www-form-urlencoded',
        'If-None-Match': '*',
    }
    resp = requests.post(f'{base_url}/items/{att_key}/file', headers=reg_headers, data=f'upload={auth["uploadKey"]}', timeout=30)
    resp.raise_for_status()
    return att_key


def upload_to_zotero(pdf: PdfDocument, config: dict[str, Any]) -> TaskResult:
    api_key = config.get('zotero_api_key', '').strip()
    user_id = config.get('zotero_user_id', '').strip()
    if not api_key or not user_id:
        return TaskResult('zotero', False, 'Missing zotero_api_key or zotero_user_id in config/env')

    base_url = _zotero_base_url(config)
    headers = _zotero_headers(api_key)
    collection_name = config.get('zotero_collection', '').strip()

    collection_key = _zotero_find_or_create_collection(base_url, headers, collection_name)
    parent_key = _zotero_create_parent_item(base_url, headers, pdf, collection_key)
    _zotero_upload_attachment(base_url, api_key, parent_key, pdf)

    details = f'Created item "{pdf.title}" with PDF attachment'
    if collection_name:
        details += f' in collection "{collection_name}"'
    return TaskResult('zotero', True, details)


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
