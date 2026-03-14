from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import requests

from .services import PdfDocument, PdfUpError, TaskResult


class ZoteroClient:
    def __init__(self, api_key: str, user_id: str | int, library_type: str = 'user'):
        self.api_key = api_key
        self.user_id = str(user_id)
        self.library_type = library_type
        self.base = f'https://api.zotero.org/{library_type}s/{self.user_id}'
        self.headers = {
            'Zotero-API-Key': self.api_key,
            'Zotero-API-Version': '3',
        }

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> 'ZoteroClient':
        api_key = config.get('zotero_api_key')
        user_id = config.get('zotero_user_id')
        library_type = config.get('zotero_library_type', 'user')
        if not api_key:
            raise PdfUpError('Missing zotero_api_key in config/env')
        if not user_id:
            raise PdfUpError('Missing zotero_user_id in config/env')
        return cls(api_key=api_key, user_id=user_id, library_type=library_type)

    def current_key_info(self) -> dict[str, Any]:
        r = requests.get('https://api.zotero.org/keys/current', headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def normalized_user_id(self) -> str:
        info = self.current_key_info()
        return str(info['userID'])

    def get_collections(self) -> list[dict[str, Any]]:
        r = requests.get(f'{self.base}/collections', headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def find_collection(self, name: str) -> dict[str, Any] | None:
        for coll in self.get_collections():
            if coll.get('data', {}).get('name') == name:
                return coll
        return None

    def create_collection(self, name: str) -> str:
        headers = self.headers | {'Content-Type': 'application/json'}
        r = requests.post(f'{self.base}/collections', headers=headers, data=json.dumps([{'name': name}]), timeout=30)
        r.raise_for_status()
        data = r.json()
        return data['successful']['0']['key']

    def resolve_collection(self, name: str) -> str:
        existing = self.find_collection(name)
        if existing:
            return existing['key']
        return self.create_collection(name)

    def create_parent_item(self, pdf: PdfDocument, collection_key: str) -> str:
        title = pdf.title
        year = None
        doi = None
        m = re.search(r'\b(19|20)\d{2}\b', pdf.text[:4000])
        if m:
            year = m.group(0)
        dm = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', pdf.text, re.I)
        if dm:
            doi = dm.group(0).rstrip('.,);]')
        item = {
            'itemType': 'journalArticle',
            'title': title,
            'date': year or '',
            'DOI': doi or '',
            'collections': [collection_key],
            'tags': [{'tag': 'pdf-up'}],
            'extra': f'Imported by pdf-up\nLocal file: {pdf.path}\nPDF hash: {pdf.content_hash}',
        }
        headers = self.headers | {'Content-Type': 'application/json'}
        r = requests.post(f'{self.base}/items', headers=headers, data=json.dumps([item]), timeout=30)
        r.raise_for_status()
        data = r.json()
        return data['successful']['0']['key']

    def create_attachment_item(self, parent_key: str, filename: str) -> str:
        item = {
            'itemType': 'attachment',
            'parentItem': parent_key,
            'linkMode': 'imported_file',
            'title': 'Full Text PDF',
            'filename': filename,
            'contentType': 'application/pdf',
        }
        headers = self.headers | {'Content-Type': 'application/json'}
        r = requests.post(f'{self.base}/items', headers=headers, data=json.dumps([item]), timeout=30)
        r.raise_for_status()
        data = r.json()
        return data['successful']['0']['key']

    def authorize_upload(self, attachment_key: str, path: Path) -> dict[str, Any]:
        headers = self.headers | {'If-None-Match': '*'}
        payload = {
            'md5': hashlib.md5(path.read_bytes()).hexdigest(),
            'filename': path.name,
            'filesize': path.stat().st_size,
            'mtime': int(path.stat().st_mtime * 1000),
            'contentType': 'application/pdf',
        }
        r = requests.post(f'{self.base}/items/{attachment_key}/file', headers=headers, data=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    def upload_binary(self, auth: dict[str, Any], path: Path) -> bool:
        if auth.get('exists') == 1:
            return False
        prefix = auth['prefix']
        suffix = auth['suffix']
        content_type = auth['contentType']
        if 'boundary=' not in content_type:
            raise PdfUpError('Missing multipart boundary in Zotero upload authorization')
        body = prefix.encode('utf-8') + path.read_bytes() + suffix.encode('utf-8')
        r = requests.post(auth['url'], data=body, headers={'Content-Type': content_type}, timeout=300)
        if r.status_code not in (200, 201, 204):
            raise PdfUpError(f'Zotero binary upload failed: {r.status_code} {r.text[:300]}')
        return True

    def finalize_upload(self, attachment_key: str, auth: dict[str, Any]) -> None:
        if auth.get('exists') == 1:
            return
        headers = self.headers | {'If-None-Match': '*'}
        r = requests.post(f'{self.base}/items/{attachment_key}/file', headers=headers, data={'upload': auth['uploadKey']}, timeout=60)
        r.raise_for_status()


def upload_to_zotero_web(pdf: PdfDocument, config: dict[str, Any]) -> TaskResult:
    client = ZoteroClient.from_config(config)
    real_user_id = client.normalized_user_id()
    client.user_id = real_user_id
    client.base = f'https://api.zotero.org/{client.library_type}s/{client.user_id}'

    collection_name = config.get('zotero_collection', '').strip() or 'pdf-up'
    collection_key = client.resolve_collection(collection_name)
    parent_key = client.create_parent_item(pdf, collection_key)
    attachment_key = client.create_attachment_item(parent_key, pdf.path.name)
    auth = client.authorize_upload(attachment_key, pdf.path)
    uploaded = client.upload_binary(auth, pdf.path)
    client.finalize_upload(attachment_key, auth)
    if uploaded:
        return TaskResult('zotero', True, f'Created item "{pdf.title}" with PDF attachment in collection "{collection_name}"')
    return TaskResult('zotero', True, f'Created item "{pdf.title}" in collection "{collection_name}"; attachment content already existed in Zotero storage')
