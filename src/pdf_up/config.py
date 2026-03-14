from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / '.config' / 'pdf-up' / 'config.json'
DEFAULT_OBSIDIAN_DIR = '/Users/home/projects/obsidian/journal'


def ensure_config_dir() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text())

    env_map = {
        'readwise_token': os.environ.get('PDF_UP_READWISE_TOKEN') or os.environ.get('READWISE_TOKEN'),
        'reader_email_account': os.environ.get('PDF_UP_READER_EMAIL_ACCOUNT'),
        'notebook_id': os.environ.get('PDF_UP_NOTEBOOK_ID'),
        'obsidian_dir': os.environ.get('PDF_UP_OBSIDIAN_DIR'),
        'reader_location': os.environ.get('PDF_UP_READER_LOCATION'),
        'reader_tags': os.environ.get('PDF_UP_READER_TAGS'),
        'summary_model': os.environ.get('PDF_UP_SUMMARY_MODEL'),
        'zotero_api_key': os.environ.get('PDF_UP_ZOTERO_API_KEY'),
        'zotero_user_id': os.environ.get('PDF_UP_ZOTERO_USER_ID'),
        'zotero_library_type': os.environ.get('PDF_UP_ZOTERO_LIBRARY_TYPE'),
        'zotero_app': os.environ.get('PDF_UP_ZOTERO_APP'),
        'zotero_collection': os.environ.get('PDF_UP_ZOTERO_COLLECTION'),
        'notebooklm_cli': os.environ.get('PDF_UP_NLM_CLI'),
        'claude_cli': os.environ.get('PDF_UP_CLAUDE_CLI'),
    }
    for key, value in env_map.items():
        if value:
            data[key] = value

    data.setdefault('obsidian_dir', DEFAULT_OBSIDIAN_DIR)
    data.setdefault('reader_location', 'new')
    data.setdefault('reader_tags', ['pdf-up'])
    if isinstance(data.get('reader_tags'), str):
        data['reader_tags'] = [tag.strip() for tag in data['reader_tags'].split(',') if tag.strip()]
    data.setdefault('summary_model', 'sonnet')
    data.setdefault('reader_email_account', 'Google')
    data.setdefault('zotero_api_key', '')
    data.setdefault('zotero_user_id', '')
    data.setdefault('zotero_library_type', 'user')
    data.setdefault('zotero_app', 'Zotero')
    data.setdefault('zotero_collection', '')
    data.setdefault('notebooklm_cli', '/Users/home/.local/bin/nlm')
    data.setdefault('claude_cli', '/Users/home/.local/bin/claude')
    return data


def save_config(data: dict[str, Any]) -> Path:
    ensure_config_dir()
    CONFIG_PATH.write_text(json.dumps(data, indent=2) + '\n')
    return CONFIG_PATH


def write_sample_config(force: bool = False) -> Path:
    ensure_config_dir()
    if CONFIG_PATH.exists() and not force:
        return CONFIG_PATH

    sample = {
        'readwise_token': 'OPTIONAL_IF_USING_EMAIL_IMPORT',
        'reader_email_account': 'Google',
        'notebook_id': 'YOUR_NOTEBOOKLM_NOTEBOOK_ID',
        'obsidian_dir': DEFAULT_OBSIDIAN_DIR,
        'reader_location': 'new',
        'reader_tags': ['pdf-up'],
        'summary_model': 'sonnet',
        'zotero_api_key': 'YOUR_ZOTERO_API_KEY',
        'zotero_user_id': '7734498',
        'zotero_library_type': 'user',
        'zotero_app': 'Zotero',
        'zotero_collection': 'amyloidosis',
        'notebooklm_cli': '/Users/home/.local/bin/nlm',
        'claude_cli': '/Users/home/.local/bin/claude'
    }
    CONFIG_PATH.write_text(json.dumps(sample, indent=2) + '\n')
    return CONFIG_PATH
