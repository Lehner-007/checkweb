import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from modules.languages import download_catalog, install_pack, ProgramIdentityError
from modules.i18n import Strings
from modules.model import ROOT

class LanguageCatalogTests(unittest.TestCase):
    def test_full_names(self):
        self.assertEqual(Strings('de').language_name('fr'),'Französisch')
        self.assertEqual(Strings('de').language_name('en'),'Englisch')
        self.assertEqual(Strings('en').language_name('de'),'German')

    def test_catalog_and_custom_language(self):
        data={'program_id':'checkweb','languages':[{'code':'de','name':'German'},{'code':'it','name':'Italiano'}]}
        with patch('modules.languages.github_json',return_value=data) as fetch:
            self.assertEqual(download_catalog('https://github.com/example/lang/'),[{'code':'it','name':'Italiano'}])
            fetch.assert_called_once_with('https://github.com/example/lang/catalog.json')

    def test_invalid_catalogs(self):
        invalid=[{}, {'program_id':'other','languages':[]}, {'program_id':'checkweb','languages':[{'code':'../../etc','name':'Bad'}]},
                 {'program_id':'checkweb','languages':[{'code':'fr','name':''}]},
                 {'program_id':'checkweb','languages':[{'code':'fr','name':'French'}]*2}]
        for data in invalid:
            with self.subTest(data=data),patch('modules.languages.github_json',return_value=data),self.assertRaises((ValueError,ProgramIdentityError)):
                download_catalog('https://github.com/example/lang')

    def test_download_failure_propagates(self):
        with patch('modules.languages.github_json',side_effect=OSError('offline')),self.assertRaises(OSError):
            download_catalog('https://github.com/example/lang')

    def test_catalog_matches_actual_packs(self):
        data=json.loads((ROOT/'github/sprachpakete/catalog.json').read_text())
        with patch('modules.languages.github_json',return_value=data): entries=download_catalog('https://github.com/example/lang')
        self.assertEqual(len(entries),8)
        for entry in entries:self.assertTrue((ROOT/'github/sprachpakete'/f"{entry['code']}.json").is_file())

    def test_custom_installed_name(self):
        pack=json.loads((ROOT/'github/sprachpakete/fr.json').read_text())
        pack.update(code='it',name='Italiano')
        with tempfile.TemporaryDirectory() as tmp:
            with patch('modules.languages.config_dir',return_value=Path(tmp)),patch('modules.i18n.config_dir',return_value=Path(tmp)):
                install_pack(pack)
                self.assertIn('it',Strings.languages())
                self.assertEqual(Strings('de').language_name('it'),'Italiano')
                with self.assertRaises(FileExistsError):install_pack(pack)
