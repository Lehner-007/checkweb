"""Precondition checks for tests that invoke the real JavaScript parser."""

import os
import shutil
import subprocess
import unittest


def require_node():
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest(
            'Node.js fehlt; Tests mit echtem JavaScript-Unterprozess wurden ausgelassen.'
        )
    return node


def require_node_acorn():
    node = require_node()
    env = os.environ.copy()
    # Do not let a user's module path or startup flags change which Acorn is tested.
    env.pop('NODE_PATH', None)
    env.pop('NODE_OPTIONS', None)
    try:
        result = subprocess.run(
            [node, '-p', "require('acorn').version"],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(
            f'Acorn-Voraussetzungsprüfung mit Node.js fehlgeschlagen ({exc}); '
            'echte Parserfälle wurden ausgelassen.'
        ) from exc
    version = result.stdout.strip()
    if result.returncode != 0 or not version:
        detail = result.stderr.strip().splitlines()
        suffix = f" Details: {detail[-1]}" if detail else ''
        raise unittest.SkipTest(
            'Acorn fehlt oder konnte nicht geladen werden; echte Parserfälle '
            f'wurden ausgelassen.{suffix}'
        )
    return node, version
