#!/usr/bin/env python3
"""Run the complete automated acceptance suite without silently skipping checks."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def preflight() -> list[str]:
    missing = []
    for module, label in (
        ('gi', 'PyGObject'), ('bs4', 'Beautiful Soup'), ('requests', 'Requests'),
        ('html5lib', 'html5lib'), ('tinycss2', 'tinycss2'), ('lxml', 'lxml'),
        ('PIL', 'Pillow'),
    ):
        try:
            __import__(module)
        except ImportError:
            missing.append(label)
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk  # noqa: F401
    except (ImportError, ValueError):
        missing.append('GTK 4 introspection bindings')
    for executable in ('php', 'node', 'acorn'):
        if not shutil.which(executable):
            missing.append(executable)
    if shutil.which('node'):
        probe = subprocess.run(
            ['node', '-e', "require('acorn'); process.stdout.write('ok')"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        if probe.returncode:
            missing.append('Node.js Modul acorn')
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        missing.append('grafische Sitzung (DISPLAY oder WAYLAND_DISPLAY)')
    return missing


def main() -> int:
    missing = preflight()
    if missing:
        print('ABNAHME UNVOLLSTÄNDIG – Voraussetzungen fehlen: ' + ', '.join(missing), file=sys.stderr)
        return 2

    print('Voraussetzungen vollständig; führe Unit- und Integrationstests aus.', flush=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        print(f'ABNAHME NICHT BESTANDEN: {len(result.failures)} fehlgeschlagen, '
              f'{len(result.errors)} Fehler, {len(result.skipped)} übersprungen.', file=sys.stderr)
        return 1

    gui_scripts = sorted((ROOT / 'tests').glob('gui_*.py'))
    for script in gui_scripts:
        print(f'GTK-Abnahme: {script.name}', flush=True)
        run = subprocess.run([sys.executable, str(script)], cwd=ROOT, timeout=90)
        if run.returncode:
            print(f'ABNAHME NICHT BESTANDEN: {script.name} mit Exit-Code {run.returncode}.', file=sys.stderr)
            return 1

    print(f'ABNAHME BESTANDEN: {result.testsRun} Unit-/Integrationstests, keine übersprungenen Tests, '
          f'{len(gui_scripts)} GTK-Abnahmeskripte.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
