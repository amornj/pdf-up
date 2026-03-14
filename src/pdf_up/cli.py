from __future__ import annotations

import argparse
import concurrent.futures
import sys
from pathlib import Path

from .config import CONFIG_PATH, load_config, write_sample_config
from .services import (
    TaskResult,
    extract_pdf,
    format_results,
    summarize_to_obsidian,
    upload_to_notebooklm,
    upload_to_readwise,
    upload_to_zotero,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='pdf-up', description='Upload a local PDF to Reader, NotebookLM, Zotero, and Obsidian summary in one command.')
    parser.add_argument('pdf_path', nargs='?', help='Local path to PDF')
    parser.add_argument('--init-config', action='store_true', help='Write a starter config file and exit')
    parser.add_argument('--config-path', action='store_true', help='Print active config path and exit')
    parser.add_argument('--notebook-id', help='Override configured NotebookLM notebook id')
    parser.add_argument('--obsidian-dir', help='Override configured Obsidian output dir')
    parser.add_argument('--summary-model', help='Override Claude model alias for summary generation')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.config_path:
        print(CONFIG_PATH)
        return 0

    if args.init_config:
        path = write_sample_config(force=False)
        print(f'Config ready at {path}')
        return 0

    if not args.pdf_path:
        parser.error('pdf_path is required unless using --init-config or --config-path')

    config = load_config()
    if args.notebook_id:
        config['notebook_id'] = args.notebook_id
    if args.obsidian_dir:
        config['obsidian_dir'] = args.obsidian_dir
    if args.summary_model:
        config['summary_model'] = args.summary_model

    pdf = extract_pdf(Path(args.pdf_path).expanduser().resolve())

    tasks = [
        ('readwise', lambda: upload_to_readwise(pdf, config)),
        ('notebooklm', lambda: upload_to_notebooklm(pdf, config)),
        ('zotero', lambda: upload_to_zotero(pdf, config)),
        ('obsidian', lambda: summarize_to_obsidian(pdf, config)),
    ]

    results: list[TaskResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(fn): name for name, fn in tasks}
        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                results.append(TaskResult(name, False, str(exc)))

    ordered = sorted(results, key=lambda r: ['readwise', 'notebooklm', 'zotero', 'obsidian'].index(r.name))
    print(format_results(ordered))
    return 0 if all(r.ok for r in ordered) else 1


if __name__ == '__main__':
    raise SystemExit(main())
