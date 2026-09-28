import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from modules.model import settings, DEFAULTS

class GitHubDefaultsTests(unittest.TestCase):
    def read_settings(self, saved):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            if saved is not None: path.write_text(json.dumps(saved))
            before = path.read_bytes() if path.exists() else None
            with patch('modules.model.config_dir', return_value=Path(tmp)):
                result = settings()
            self.assertEqual(path.read_bytes() if path.exists() else None, before)
            return result

    def test_new_install(self):
        result = self.read_settings(None)
        self.assertEqual(result['update_url'], 'https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/version.json')
        self.assertEqual(result['source_url'], 'https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/sprachpakete')
        self.assertFalse(result['update_check'])

    def test_old_empty_configuration(self):
        result = self.read_settings({'config_version': 1, 'source_url': '', 'update_url': '', 'language': 'en'})
        self.assertEqual(result['source_url'], DEFAULTS['source_url'])
        self.assertEqual(result['update_url'], DEFAULTS['update_url'])
        self.assertEqual(result['language'], 'en')
        self.assertEqual(result['config_version'], 2)

    def test_custom_urls_preserved(self):
        result = self.read_settings({'config_version': 1, 'source_url': 'https://example.org/lang', 'update_url': 'https://example.org/version'})
        self.assertEqual(result['source_url'], 'https://example.org/lang')
        self.assertEqual(result['update_url'], 'https://example.org/version')

    def test_new_explicit_empty_configuration_preserved(self):
        result = self.read_settings({'config_version': 2, 'source_url': '', 'update_url': ''})
        self.assertEqual(result['source_url'], '')
        self.assertEqual(result['update_url'], '')
