import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from modules.model import ROOT, Report
from modules.reports import check_export_target, save_report


class ExportProtectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.path = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'CHECKWEB_DEV': '0', 'XDG_CONFIG_HOME': str(self.path / 'config')})
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()

    def test_resources_config_and_symlinks_rejected_before_write(self):
        targets = [ROOT / name / 'example.json' for name in ('lang', 'help', 'assets', 'modules', 'github', 'packaging')]
        targets += [ROOT / 'VERSION', ROOT / 'checkweb.py', self.path / 'config/checkweb/settings.json']
        alias = self.path / 'alias'
        alias.symlink_to(ROOT / 'lang', target_is_directory=True)
        targets.append(alias / 'en.json')
        for target in targets:
            with self.subTest(target=target), self.assertRaises(ValueError):
                check_export_target(target)
        config = self.path / 'config/checkweb/settings.json'
        config.parent.mkdir(parents=True); config.write_text('original')
        with self.assertRaises(ValueError): save_report(None, config)
        self.assertEqual(config.read_text(), 'original')

    def test_normal_report_can_be_replaced(self):
        from modules.engine import Scanner
        from modules.model import DEFAULTS
        source = self.path / 'site'; source.mkdir()
        (source / 'index.html').write_text('<html><body>Test</body></html>')
        report = Scanner('local', source, dict(DEFAULTS, external_links=False)).run()
        target = self.path / 'report.json'; target.write_text('old')
        save_report(report, target)
        import json
        self.assertEqual(json.loads(target.read_text())['status'], report.status)

    def test_cli_rejects_active_configuration_without_traceback(self):
        import subprocess, sys
        source = self.path / 'site'; source.mkdir()
        (source / 'index.html').write_text('<html><body>Test</body></html>')
        config = self.path / 'config/checkweb/settings.json'
        config.parent.mkdir(parents=True); config.write_text('{}')
        result = subprocess.run([sys.executable, str(ROOT / 'checkweb.py'), '--local', str(source),
                                 '--no-network', '--output', str(config), '--language', 'de'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIn('nicht', result.stderr)
        self.assertEqual(config.read_text(), '{}')
