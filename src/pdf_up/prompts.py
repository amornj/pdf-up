from __future__ import annotations

from typing import Any

from .notebooks import find_notebook_matches, notebook_name_from_id, resolve_notebook_id_by_name
from .services import PdfUpError


def prompt_with_default(label: str, current: str) -> str:
    value = input(f'{label} [{current}]: ').strip()
    return value or current


def resolve_notebook_interactively(nlm_path: str, notebook_input: str) -> tuple[str, str]:
    try:
        return resolve_notebook_id_by_name(nlm_path, notebook_input)
    except PdfUpError as exc:
        if str(exc) != 'MULTIPLE_MATCHES':
            raise

    matches = find_notebook_matches(nlm_path, notebook_input)
    print('\nMultiple NotebookLM notebooks matched:')
    for i, nb in enumerate(matches, 1):
        print(f'  {i}. {nb.get("title")} ({nb.get("id")})')
    choice = input('Choose notebook number: ').strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(matches)):
        raise PdfUpError('Invalid notebook selection')
    nb = matches[int(choice) - 1]
    return nb['id'], nb['title']


def interactive_resolve(config: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(config)
    nlm_path = cfg.get('notebooklm_cli', '/Users/home/.local/bin/nlm')
    current_notebook_id = cfg.get('notebook_id', '')
    current_notebook_name = ''
    if current_notebook_id and current_notebook_id != 'YOUR_NOTEBOOKLM_NOTEBOOK_ID':
        current_notebook_name = notebook_name_from_id(nlm_path, current_notebook_id)

    print()
    cfg['obsidian_dir'] = prompt_with_default('Obsidian folder', cfg.get('obsidian_dir', ''))
    notebook_default = current_notebook_name or 'amyloidosis'
    notebook_input = prompt_with_default('NotebookLM notebook', notebook_default)
    resolved_id, resolved_name = resolve_notebook_interactively(nlm_path, notebook_input)
    cfg['notebook_id'] = resolved_id
    cfg['notebook_name'] = resolved_name
    cfg['zotero_collection'] = prompt_with_default('Zotero collection', cfg.get('zotero_collection', ''))

    print('\nResolved settings:')
    print(f"- Obsidian folder: {cfg['obsidian_dir']}")
    print(f"- NotebookLM notebook: {cfg['notebook_name']} ({cfg['notebook_id']})")
    print(f"- Zotero collection: {cfg['zotero_collection']}")
    proceed = input('Proceed? [Y/n]: ').strip().lower()
    if proceed in {'n', 'no'}:
        raise SystemExit(1)
    return cfg
