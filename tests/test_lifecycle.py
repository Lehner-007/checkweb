import logging
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch
from modules.lifecycle import execute_logged, set_log_language, log_text


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        language = patch('modules.lifecycle.settings', return_value={'language':'de'})
        language.start();self.addCleanup(language.stop)
        self.addCleanup(set_log_language, 'de')
        self.config = patch('modules.lifecycle.config_dir', return_value=self.path)
        self.config.start();self.addCleanup(self.config.stop)

    def log(self):
        return (self.path / 'logs/checkweb.log').read_text()

    def test_start_normal_end_and_no_duplicate_handlers(self):
        handlers = list(logging.getLogger().handlers)
        self.assertEqual(execute_logged(lambda: 0, 'GUI'), 0)
        text = self.log()
        self.assertIn('Programm gestartet', text)
        self.assertIn('normal beendet', text)
        self.assertIn('Exit-Code=0', text)
        self.assertIn('Laufzeit=', text)
        self.assertRegex(text, r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[+-]\d{4}')
        self.assertEqual(logging.getLogger().handlers, handlers)

    def test_error_exit(self):
        self.assertEqual(execute_logged(lambda: 2, 'CLI lokal'), 2)
        self.assertIn('Exit-Code=2', self.log())

    def test_keyboard_interrupt(self):
        def interrupt(): raise KeyboardInterrupt()
        self.assertEqual(execute_logged(interrupt, 'GUI'), 130)
        self.assertIn('Benutzerabbruch', self.log())

    def test_exception_logged_without_secret(self):
        def fail(): raise RuntimeError('geheimes-passwort')
        with self.assertRaises(RuntimeError): execute_logged(fail, 'GUI')
        self.assertIn('RuntimeError', self.log())
        self.assertNotIn('geheimes-passwort', self.log())

    def test_sigterm_and_restore(self):
        original = signal.getsignal(signal.SIGTERM)
        with self.assertRaises(SystemExit) as caught:
            execute_logged(lambda: os.kill(os.getpid(), signal.SIGTERM), 'GUI')
        self.assertEqual(caught.exception.code, 143)
        self.assertIn('Signal SIGTERM', self.log())
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)

    def test_saved_english_and_explicit_override(self):
        with patch('modules.lifecycle.settings', return_value={'language':'en'}):
            execute_logged(lambda: 0, 'CLI lokal')
        text = self.log()
        self.assertIn('Application started', text)
        self.assertIn('Mode=CLI local', text)
        self.assertIn('Reason=normal shutdown', text)
        self.assertNotIn('Programm', text)
        execute_logged(lambda: 0, 'GUI', 'en')
        self.assertEqual(self.log().count('Application started'), 2)

    def test_switch_changes_new_messages_only(self):
        def operation():
            logging.warning(log_text('log_scan_worker'))
            set_log_language('en')
            logging.warning(log_text('log_scan_worker'))
            return 0
        execute_logged(operation, 'GUI', 'de')
        text = self.log()
        self.assertIn('Programm gestartet', text)
        self.assertIn('Prüfung fehlgeschlagen', text)
        self.assertIn('Scan worker failed', text)
        self.assertIn('Application stopped', text)
        self.assertNotIn('Programm beendet', text)

    def test_unwritable_log_does_not_block(self):
        with patch('modules.lifecycle.config_dir', side_effect=PermissionError):
            self.assertEqual(execute_logged(lambda: 0, 'GUI'), 0)


if __name__ == '__main__': unittest.main()
