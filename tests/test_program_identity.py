"""Reject wrong-project documents before installation or version acceptance."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from modules.languages import (ProgramIdentityError, import_pack, download_pack,
                               download_version, validate_version, validate_pack)
from modules.i18n import Strings,fields
from modules.model import ROOT,VERSION

class ProgramIdentityTests(unittest.TestCase):
    def pack(self, **extra):
        return dict(program_id='checkweb',code='fr',strings={'start':'Démarrer'},
                    help_html='<html><h1>Aide</h1></html>',**extra)

    def invalid_documents(self, valid):
        missing=valid.copy();missing.pop('program_id')
        yield missing
        for value in ('another-project','CheckWeb','checkweb ',None,1,[],{}):
            yield dict(valid,program_id=value)
        yield []
        yield None

    def test_local_import_rejects_foreign_and_missing_identity_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config';source=Path(tmp)/'pack.json'
            for data in self.invalid_documents(self.pack()):
                with self.subTest(data=data),patch('modules.languages.config_dir',return_value=config):
                    source.write_text(json.dumps(data))
                    with self.assertRaises(ProgramIdentityError):import_pack(source)
                    self.assertFalse(config.exists())

    def test_download_rejects_foreign_and_missing_identity_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config'
            for data in self.invalid_documents(self.pack()):
                with self.subTest(data=data),patch('modules.languages.github_json',return_value=data),patch('modules.languages.config_dir',return_value=config):
                    with self.assertRaises(ProgramIdentityError):download_pack('https://raw.githubusercontent.com/example/repo/main/lang','fr')
                    self.assertFalse(config.exists())

    def test_matching_download_installs_both_files_and_keeps_existing_pack(self):
        with tempfile.TemporaryDirectory() as tmp,patch('modules.languages.config_dir',return_value=Path(tmp)),patch('modules.languages.github_json',return_value=self.pack()) as fetch:
            self.assertEqual(download_pack('https://raw.githubusercontent.com/example/repo/main/lang/','fr'),'fr')
            fetch.assert_called_once_with('https://raw.githubusercontent.com/example/repo/main/lang/fr.json')
            folder=Path(tmp)/'languages/fr'
            self.assertEqual(json.loads((folder/'strings.json').read_text()),{'start':'Démarrer'})
            self.assertIn('Aide',(folder/'help.html').read_text())
            before={p.name:p.read_bytes() for p in folder.iterdir()}
            with self.assertRaises(FileExistsError):download_pack('https://raw.githubusercontent.com/example/repo/main/lang','fr')
            self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})

    def test_version_download_requires_identity(self):
        for data in self.invalid_documents({'program_id':'checkweb','version':'999.0.0'}):
            with self.subTest(data=data),patch('modules.languages.github_json',return_value=data):
                with self.assertRaises(ProgramIdentityError):download_version('https://raw.githubusercontent.com/example/repo/main/version.json')
        with patch('modules.languages.github_json',return_value={'program_id':'checkweb','version':'1.2.3'}):
            self.assertEqual(download_version('https://raw.githubusercontent.com/example/repo/main/version.json'),'1.2.3')

    def test_versions_must_follow_project_schema(self):
        for value in ('',None,1,'1.2','v1.2.3','1.2.3\n','01.2.3',{},'1.2.3-other'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_version({'program_id':'checkweb','version':value})

    def test_prepared_resources_match_program(self):
        self.assertEqual(validate_version(json.loads((ROOT/'github/version.json').read_text())),VERSION)
        en=Strings('en').en
        packs=[p for p in (ROOT/'github/sprachpakete').glob('*.json') if p.name!='catalog.json']
        self.assertEqual(len(packs),8)
        for path in packs:
            data=json.loads(path.read_text());code,strings,help_html=validate_pack(data)
            with self.subTest(code=code):
                self.assertEqual(data['application_version'],VERSION)
                self.assertEqual(set(strings),set(en))
                self.assertIn('program_id',help_html)
                for key in en:self.assertEqual(fields(strings[key]),fields(en[key]))

if __name__=='__main__':unittest.main()
