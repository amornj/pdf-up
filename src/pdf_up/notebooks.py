from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .services import PdfUpError


def list_notebooks(nlm_path: str) -> list[dict[str, Any]]:
    if not shutil.which(nlm_path) and not Path(nlm_path).exists():
        raise PdfUpError(f'NotebookLM CLI not found: {nlm_path}')
    proc = subprocess.run([nlm_path, 'notebook', 'list', '--json'], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise PdfUpError(f'Unable to list NotebookLM notebooks: {(proc.stderr or proc.stdout).strip()[:400]}')
    return json.loads(proc.stdout)


def notebook_name_from_id(nlm_path: str, notebook_id: str) -> str:
    for nb in list_notebooks(nlm_path):
        if nb.get('id') == notebook_id:
            return nb.get('title', notebook_id)
    return notebook_id


def resolve_notebook_id_by_name(nlm_path: str, name: str) -> tuple[str, str]:
    notebooks = list_notebooks(nlm_path)
    exact = [nb for nb in notebooks if nb.get('title') == name]
    if len(exact) == 1:
        nb = exact[0]
        return nb['id'], nb['title']

    lower = [nb for nb in notebooks if nb.get('title', '').lower() == name.lower()]
    if len(lower) == 1:
        nb = lower[0]
        return nb['id'], nb['title']

    contains = [nb for nb in notebooks if name.lower() in nb.get('title', '').lower()]
    if len(contains) == 1:
        nb = contains[0]
        return nb['id'], nb['title']
    if len(contains) > 1:
        options = ', '.join(f"{nb.get('title')} ({nb.get('id')})" for nb in contains[:8])
        raise PdfUpError(f'Multiple NotebookLM notebooks match "{name}": {options}')

    raise PdfUpError(f'No NotebookLM notebook matched name: {name}')
