import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
import subprocess
from unittest.mock import patch

from modules import jsrefs
from prerequisites import require_node, require_node_acorn


FAKE_NODE = '''#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time

mode = os.environ.get("CHECKWEB_FAKE_PARSER_MODE", "ok")
if mode == "blocked_input":
    time.sleep(30)
elif mode == "silent":
    sys.stdin.buffer.read()
    time.sleep(30)
elif mode == "large_output":
    sys.stdin.buffer.read()
    sys.stdout.write("x" * (300_000))
    sys.stdout.flush()
elif mode == "descendant":
    sys.stdin.buffer.read()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    with open(os.environ["CHECKWEB_FAKE_CHILD_PID"], "w") as stream:
        stream.write(str(child.pid))
    print(json.dumps({"ok": True}), flush=True)
elif mode == "long_sleep":
    with open(os.environ["CHECKWEB_FAKE_CHILD_PID"], "w") as stream:
        stream.write(str(os.getpid()))
    time.sleep(30)
elif mode == "ok":
    sys.stdin.buffer.read()
    print(json.dumps({"ok": True, "refs": []}), flush=True)
'''


class ParserProcessLimitTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.real_node = shutil.which('node')
        self.node = Path(self.folder.name) / 'node'
        self.node.write_text(FAKE_NODE)
        self.node.chmod(0o755)
        self.which = patch('modules.jsrefs.shutil.which', return_value=str(self.node))
        self.which.start()
        self.addCleanup(self.which.stop)
        self.addCleanup(self.folder.cleanup)

    def test_normal_child_returns_json(self):
        with patch.dict(os.environ, {'CHECKWEB_FAKE_PARSER_MODE': 'ok'}):
            self.assertEqual(jsrefs.parse('let x = 1;'), {'ok': True, 'refs': []})

    def test_missing_node_is_reported_as_unavailable(self):
        with patch('modules.jsrefs.shutil.which', return_value=None):
            with self.assertRaises(jsrefs.ParserUnavailable):
                jsrefs.parse('let x = 1;')

    def test_missing_acorn_is_reported_by_adapter(self):
        require_node()
        missing_helper = Path(self.folder.name) / 'missing-acorn.cjs'
        missing_helper.write_text(
            "try { require('checkweb_test_missing_acorn'); } "
            "catch (_) { process.stdout.write(JSON.stringify({unavailable:true})); }"
        )
        with patch('modules.jsrefs.shutil.which', return_value=self.real_node), \
                patch('modules.jsrefs.HELPER', missing_helper):
            self.assertEqual(jsrefs.parse('let x = 1;'), {'unavailable': True})

    def test_real_acorn_handles_nested_source_without_hanging(self):
        node, _version = require_node_acorn()
        with patch('modules.jsrefs.shutil.which', return_value=node), \
                patch('modules.jsrefs.HELPER', jsrefs.ROOT / 'modules' / 'jsparser.cjs'):
            started = time.monotonic()
            result = jsrefs.parse('const nested=' + '(' * 1000 + '1' + ')' * 1000 + ';', 'script')
        self.assertLess(time.monotonic() - started, jsrefs.PARSER_TIMEOUT + 0.5)
        self.assertIsInstance(result, dict)
        if result.get('ok') is True:
            self.assertEqual(result.get('refs'), [])
        else:
            self.assertTrue(result.get('error') or result.get('limit'), result)

    def test_deadline_applies_while_child_stays_silent_after_reading(self):
        with patch.dict(os.environ, {'CHECKWEB_FAKE_PARSER_MODE': 'silent'}), \
                patch('modules.jsrefs.PARSER_TIMEOUT', 0.15):
            started = time.monotonic()
            with self.assertRaisesRegex(jsrefs.ParserLimit, 'parser_timeout'):
                jsrefs.parse('small input')
            self.assertLess(time.monotonic() - started, 0.15 + 0.5)

    def test_deadline_applies_while_child_does_not_read_large_input(self):
        with patch.dict(os.environ, {'CHECKWEB_FAKE_PARSER_MODE': 'blocked_input'}), \
                patch('modules.jsrefs.PARSER_TIMEOUT', 0.15):
            started = time.monotonic()
            with self.assertRaisesRegex(jsrefs.ParserLimit, 'parser_timeout'):
                jsrefs.parse('x' * jsrefs.MAX_SOURCE_BYTES)
            self.assertLess(time.monotonic() - started, 0.15 + 0.5)

    def test_parser_works_again_after_timeout(self):
        node, _version = require_node_acorn()
        with patch.dict(os.environ, {'CHECKWEB_FAKE_PARSER_MODE': 'silent'}), \
                patch('modules.jsrefs.PARSER_TIMEOUT', 0.15):
            with self.assertRaises(jsrefs.ParserLimit):
                jsrefs.parse('first')
        with patch('modules.jsrefs.shutil.which', return_value=node), \
                patch('modules.jsrefs.HELPER', jsrefs.ROOT / 'modules' / 'jsparser.cjs'):
            self.assertTrue(jsrefs.parse('const next = 1;', 'script')['ok'])

    def test_acorn_precheck_reports_missing_prerequisites_without_keyerror(self):
        import prerequisites
        from subprocess import CompletedProcess

        with patch('prerequisites.shutil.which', return_value=None):
            with self.assertRaises(unittest.SkipTest) as missing_node:
                prerequisites.require_node_acorn()
        self.assertIn('Node.js fehlt', str(missing_node.exception))

        failed = CompletedProcess(['node', '-p'], 1, '', "Cannot find module 'acorn'")
        with patch('prerequisites.shutil.which', return_value='/usr/bin/node'), \
                patch('prerequisites.subprocess.run', return_value=failed):
            with self.assertRaises(unittest.SkipTest) as missing_acorn:
                prerequisites.require_node_acorn()
        self.assertIn('Acorn fehlt', str(missing_acorn.exception))

    def test_cancellation_applies_while_child_does_not_read(self):
        cancel = threading.Event()
        timer = threading.Timer(0.12, cancel.set)
        timer.start()
        try:
            with patch.dict(os.environ, {'CHECKWEB_FAKE_PARSER_MODE': 'blocked_input'}), \
                    patch('modules.jsrefs.PARSER_TIMEOUT', 3):
                started = time.monotonic()
                with self.assertRaises(InterruptedError):
                    jsrefs.parse('x' * jsrefs.MAX_SOURCE_BYTES, cancel=cancel)
                self.assertLess(time.monotonic() - started, 2)
        finally:
            timer.cancel()
            timer.join()

    def test_output_limit_is_enforced(self):
        with patch.dict(os.environ, {'CHECKWEB_FAKE_PARSER_MODE': 'large_output'}):
            with self.assertRaisesRegex(jsrefs.ParserLimit, 'parser_output'):
                jsrefs.parse('x')

    def test_timeout_kills_descendant_holding_stdout_open(self):
        child_pid_file = Path(self.folder.name) / 'child.pid'
        with patch.dict(os.environ, {
            'CHECKWEB_FAKE_PARSER_MODE': 'descendant',
            'CHECKWEB_FAKE_CHILD_PID': str(child_pid_file),
        }), patch('modules.jsrefs.PARSER_TIMEOUT', 0.2):
            started = time.monotonic()
            with self.assertRaisesRegex(jsrefs.ParserLimit, 'parser_timeout'):
                jsrefs.parse('x')
            self.assertLess(time.monotonic() - started, 2)

        child_pid = int(child_pid_file.read_text())
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                state = Path(f'/proc/{child_pid}/stat').read_text().split()[2]
            except FileNotFoundError:
                break
            if state == 'Z':
                break
            time.sleep(0.02)
        else:
            self.fail('parser descendant remained alive after timeout')

    def test_scan_worker_sigkill_does_not_orphan_parser(self):
        child_pid_file = Path(self.folder.name) / 'parser.pid'
        worker_code = (
            'import subprocess,sys,time; '
            'subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]], '
            'stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL, '
            'start_new_session=True); time.sleep(30)'
        )
        env = dict(os.environ, CHECKWEB_FAKE_PARSER_MODE='long_sleep',
                   CHECKWEB_FAKE_CHILD_PID=str(child_pid_file))
        worker = subprocess.Popen(
            [sys.executable, '-c', worker_code,
             str(Path(jsrefs.__file__).with_name('jsparser_launcher.py')), str(self.node)],
            env=env, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 2
            while not child_pid_file.exists() and time.monotonic() < deadline:
                if worker.poll() is not None:
                    self.fail('test scan worker exited before starting parser')
                time.sleep(0.02)
            self.assertTrue(child_pid_file.exists(), 'parser did not start')
            parser_pid = int(child_pid_file.read_text())
            worker.kill()
            worker.wait(timeout=2)
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try:
                    state = Path(f'/proc/{parser_pid}/stat').read_text().split()[2]
                except FileNotFoundError:
                    break
                if state == 'Z':
                    break
                time.sleep(0.02)
            else:
                self.fail('parser remained alive after its scan worker was killed')
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=2)


if __name__ == '__main__':
    unittest.main()
