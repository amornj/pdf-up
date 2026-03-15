from __future__ import annotations

import json
import re
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
            'tags': [{'tag': 'pdf-up'}, {'tag': 'metadata-only'}],
            'extra': f'Imported by pdf-up\nLocal file: {pdf.path}\nPDF hash: {pdf.content_hash}\nFull PDF stored in Reader / NotebookLM',
        }
        headers = self.headers | {'Content-Type': 'application/json'}
        r = requests.post(f'{self.base}/items', headers=headers, data=json.dumps([item]), timeout=30)
        r.raise_for_status()
        data = r.json()
        return data['successful']['0']['key']


def upload_to_zotero_web(pdf: PdfDocument, config: dict[str, Any]) -> TaskResult:
    client = ZoteroClient.from_config(config)
    real_user_id = client.normalized_user_id()
    client.user_id = real_user_id
    client.base = f'https://api.zotero.org/{client.library_type}s/{client.user_id}'

    collection_name = config.get('zotero_collection', '').strip() or 'pdf-up'
    collection_key = client.resolve_collection(collection_name)
    parent_key = client.create_parent_item(pdf, collection_key)
    return TaskResult('zotero', True, f'Created metadata-only Zotero item in collection "{collection_name}" (item {parent_key})')
