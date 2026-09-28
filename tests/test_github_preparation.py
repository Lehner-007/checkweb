"""Isolated source preparation and publication tests; never contact GitHub."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
GIT=shutil.which('git')

@unittest.skipUnless(GIT,'Git is required for publication-script tests')
class GitHubPreparationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.base=Path(self.tmp.name);self.root=self.base/'project';self.root.mkdir()
  for name in ('erstellegithub.sh','erstellezip.sh','.gitignore','LICENSE'):
   shutil.copy2(ROOT/name,self.root/name)
  (self.root/'VERSION').write_text('4.5.6\n')
  (self.root/'README.md').write_text('# Fixture\n')
  (self.root/'checkweb.py').write_text('print("fixture")\n')
  (self.root/'tests').mkdir();(self.root/'tests/test_fixture.py').write_text('# fixture\n')
  self.env=os.environ.copy()
  self.env['GIT_CEILING_DIRECTORIES']=str(self.base)  # Fixtures must not inherit the enclosing project repository.
  # Redirect *all* test GitHub URL arguments to this local bare repository.
  self.remote=self.base/'remote.git'
  subprocess.run([GIT,'init','--bare','--quiet',str(self.remote)],check=True)
  binpath=self.base/'bin';binpath.mkdir()
  shim=binpath/'git'
  shim.write_text('''#!/usr/bin/python3
import json,os,subprocess,sys
args=sys.argv[1:]
with open(os.environ['CW_GIT_LOG'],'a') as f:f.write(json.dumps(args)+'\\n')
args=[os.environ['CW_LOCAL_REMOTE'] if x=='git@github.com:example/checkweb.git' else x for x in args]
sys.exit(subprocess.run([os.environ['CW_REAL_GIT'],*args]).returncode)
''')
  shim.chmod(0o755)
  self.env.update(PATH=str(binpath)+os.pathsep+self.env['PATH'],CW_GIT_LOG=str(self.base/'git.log'),CW_LOCAL_REMOTE=str(self.remote),CW_REAL_GIT=GIT)
 def run_script(self,*args,input=''):
  return subprocess.run([str(self.root/'erstellegithub.sh'),*args],input=input,text=True,capture_output=True,env=self.env,cwd=self.base,timeout=30)
 def git(self,*args):
  return subprocess.run([GIT,'-C',str(self.root),*args],check=True,capture_output=True,text=True).stdout.strip()
 def init_repo(self,commit=False):
  self.git('init','--quiet','--initial-branch=main')
  self.git('config','user.name','Release Test');self.git('config','user.email','test@example.invalid')
  self.git('remote','add','origin','git@github.com:example/checkweb.git')
  if commit:self.git('add','.');self.git('commit','--quiet','-m','Initial test fixture')
 def snapshot(self):
  return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file() and not {'dist','.git'}&set(p.relative_to(self.root).parts)}
 def test_version_and_inventory_exclusions_preserve_sources(self):
  for folder in ('.venv','__pycache__','.config','dist','logs'):
   (self.root/folder).mkdir();(self.root/folder/'local.pyc').write_text('private fixture')
  before=self.snapshot();result=self.run_script()
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn('Checkweb 4.5.6',result.stdout)
  stage=next((self.root/'dist').glob('checkweb-github-4.5.6-*'))
  self.assertEqual({str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()}, {'VERSION','README.md','LICENSE','checkweb.py','erstellezip.sh','erstellegithub.sh','.gitignore','tests/test_fixture.py'})
  self.assertEqual(self.snapshot(),before)
  self.assertFalse((self.root/'.git').exists())
 def test_deb_sources_included_and_private_error_list_excluded(self):
  (self.root/'erstelledeb.sh').write_text('#!/bin/sh\n')
  (self.root/'packaging').mkdir()
  (self.root/'packaging/build_deb.py').write_text('# public build script\n')
  (self.root/'fehler.txt').write_text('private local notes\n')
  result=self.run_script()
  self.assertEqual(result.returncode,0,result.stderr)
  stage=next((self.root/'dist').glob('checkweb-github-4.5.6-*'))
  self.assertTrue((stage/'erstelledeb.sh').is_file())
  self.assertTrue((stage/'packaging/build_deb.py').is_file())
  self.assertFalse((stage/'fehler.txt').exists())
 def test_missing_required_files_and_tests_fail(self):
  for name in ('VERSION','LICENSE','README.md','checkweb.py','.gitignore','tests/test_fixture.py'):
   with self.subTest(name=name):
    p=self.root/name;data=p.read_bytes();p.unlink()
    result=self.run_script();self.assertNotEqual(result.returncode,0)
    self.assertIn(name if '/' not in name else 'tests',result.stderr)
    p.write_bytes(data)
 def test_empty_and_invalid_versions_fail(self):
  for value in ('','1.2','v1.2.3','01.2.3','1.2.3\nextra'):
   with self.subTest(value=value):
    (self.root/'VERSION').write_text(value)
    result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('VERSION',result.stderr)
 def test_env_and_secret_files_abort_without_deleting(self):
  cases={'.env':'harmless fixture','docs/id_rsa':'fixture','modules/config.py':'api_key = "'+'ghp_'+'A'*30+'"\n'}
  for name,content in cases.items():
   with self.subTest(name=name):
    p=self.root/name;p.parent.mkdir(exist_ok=True);p.write_text(content)
    result=self.run_script();self.assertNotEqual(result.returncode,0)
    self.assertIn(name,result.stderr);self.assertNotIn('A'*30,result.stderr)
    self.assertEqual(p.read_text(),content);p.unlink()
 def test_source_symlink_is_rejected(self):
  (self.root/'assets').mkdir();(self.root/'assets/secret.txt').symlink_to(self.root/'LICENSE')
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('assets/secret.txt',result.stderr)
 def test_unknown_file_aborts(self):
  (self.root/'private-report.html').write_text('private report')
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('private-report.html',result.stderr)
 def test_publish_requires_repository(self):
  result=self.run_script('--publish');self.assertNotEqual(result.returncode,0);self.assertIn('Git-Repository',result.stderr)
 def test_existing_tag_detected_and_preserved(self):
  self.init_repo(commit=True);self.git('tag','v4.5.6');before=self.git('rev-parse','v4.5.6')
  prepared=self.run_script();self.assertEqual(prepared.returncode,0,prepared.stderr);self.assertIn('bereits vorhanden',prepared.stdout)
  result=self.run_script('--publish',input='VERÖFFENTLICHEN 4.5.6\n')
  self.assertNotEqual(result.returncode,0);self.assertIn('existiert bereits',result.stderr)
  self.assertEqual(self.git('rev-parse','v4.5.6'),before)
 def test_no_confirmation_means_no_commit_tag_or_push(self):
  self.init_repo()
  for answer in ('','nein\n','ja\n'):
   with self.subTest(answer=answer):
    result=self.run_script('--publish',input=answer);self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertIn('Keine ausdrückliche Bestätigung',result.stderr)
    self.assertEqual(self.git('tag','--list'),'')
  commands=[json.loads(x) for x in (self.base/'git.log').read_text().splitlines()]
  for cmd in commands:
   verb=cmd[cmd.index('-C')+2]
   self.assertNotIn(verb,('add','commit','tag','push'))
  self.assertFalse((self.root/'.git/index').exists())
 def test_confirmed_publication_only_reaches_local_test_remote(self):
  self.init_repo();result=self.run_script('--publish',input='VERÖFFENTLICHEN 4.5.6\n')
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertEqual(self.git('log','-1','--format=%s'),'Release Checkweb 4.5.6')
  refs=subprocess.check_output([GIT,'--git-dir',str(self.remote),'show-ref'],text=True)
  self.assertIn('refs/heads/main',refs);self.assertIn('refs/tags/v4.5.6',refs)
  self.assertIn('erfolgreich veröffentlicht',result.stdout)
 def test_remote_tag_is_not_overwritten(self):
  self.init_repo(commit=True)
  self.git('tag','v4.5.6');self.git('push',str(self.remote),'refs/tags/v4.5.6');self.git('tag','-d','v4.5.6')
  result=self.run_script('--publish',input='VERÖFFENTLICHEN 4.5.6\n')
  self.assertNotEqual(result.returncode,0);self.assertIn('auf dem Remote',result.stderr);self.assertEqual(self.git('tag','--list'),'')
 def test_secret_in_deleted_history_is_rejected(self):
  self.init_repo()
  secret=self.root/'.env';secret.write_text('fixture')
  self.git('add','-f','.env');self.git('commit','--quiet','-m','Fixture secret')
  self.git('rm','.env');self.git('commit','--quiet','-m','Fixture removal')
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('Git-Historie: .env',result.stderr)
 def test_forbidden_tracked_file_is_rejected(self):
  self.init_repo();(self.root/'.config').mkdir();(self.root/'.config/settings.json').write_text('{}')
  self.git('add','-f','.config/settings.json')
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('.config/settings.json',result.stderr)
 def test_publish_requires_remote_and_branch(self):
  self.init_repo(commit=True)
  self.git('remote','remove','origin')
  result=self.run_script('--publish');self.assertNotEqual(result.returncode,0);self.assertIn('Remote origin',result.stderr)
  self.git('remote','add','origin','git@github.com:example/checkweb.git')
  self.git('checkout','--detach')
  result=self.run_script('--publish');self.assertNotEqual(result.returncode,0);self.assertIn('Branch',result.stderr)
 def test_mismatched_staged_change_is_not_overwritten(self):
  self.init_repo(commit=True)
  p=self.root/'README.md';p.write_text('staged fixture');self.git('add','README.md')
  p.write_text('different working fixture')
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('Gestagte Änderungen',result.stderr)
  self.assertEqual(self.git('show',':README.md'),'staged fixture')
  self.assertEqual(p.read_text(),'different working fixture')
 def test_wrong_license_and_linked_output_fail(self):
  original=(self.root/'LICENSE').read_bytes();(self.root/'LICENSE').write_text('Different license')
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('LICENSE',result.stderr)
  (self.root/'LICENSE').write_bytes(original)
  (self.root/'dist').symlink_to(self.base,target_is_directory=True)
  result=self.run_script();self.assertNotEqual(result.returncode,0);self.assertIn('dist',result.stderr)
 def test_failed_push_preserves_local_tag_and_reports_failure(self):
  self.init_repo()
  subprocess.run([GIT,'--git-dir',str(self.remote),'config','receive.denyNonFastForwards','true'],check=True)
  hook=self.remote/'hooks/pre-receive';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
  result=self.run_script('--publish',input='VERÖFFENTLICHEN 4.5.6\n')
  self.assertNotEqual(result.returncode,0);self.assertIn('push',result.stderr)
  self.assertNotIn('erfolgreich veröffentlicht',result.stdout)
  self.assertEqual(self.git('tag','--list'),'v4.5.6')
  refs=subprocess.run([GIT,'--git-dir',str(self.remote),'show-ref'],capture_output=True,text=True)
  self.assertEqual(refs.stdout,'')
 def test_existing_ignore_rules_are_copied(self):
  p=self.root/'.gitignore';p.write_text(p.read_text()+'\nexisting-local-rule/\n')
  result=self.run_script();self.assertEqual(result.returncode,0,result.stderr)
  stage=next((self.root/'dist').glob('checkweb-github-*'))
  self.assertEqual((stage/'.gitignore').read_bytes(),p.read_bytes())

if __name__=='__main__':unittest.main()
