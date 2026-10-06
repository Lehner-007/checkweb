import json
import shutil
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from modules.engine import Scanner,canonical
from modules.model import DEFAULTS,CATEGORIES
from modules.reports import save_report
from modules.languages import validate_pack,install_pack
from modules.i18n import Strings

VALID=b'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="description" content="test"><title>Test</title></head><body><h1 id="ok">Test</h1></body></html>'

class LocalTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.opts=dict(DEFAULTS,categories=list(CATEGORIES),external_links=False,robots=False,delay=.05)
 def tearDown(self):self.temp.cleanup()
 def scan(self):return Scanner('local',self.root,self.opts).run()
 def test_valid_html(self):
  try:
   import html5lib
  except ImportError:
   self.skipTest('Optional HTML checker unavailable: python3-html5lib')
  (self.root/'index.html').write_bytes(VALID)
  report=self.scan()
  self.assertEqual(report.status,'complete')
  self.assertEqual([f.code for f in report.findings],[])
 def test_valid_html_without_html5lib_is_incomplete(self):
  (self.root/'index.html').write_bytes(VALID)
  self.opts['categories']=['html']
  # Exercise the real ImportError path even when html5lib is installed.
  with patch.dict('sys.modules',{'html5lib':None}):
   report=self.scan()
  self.assertEqual(report.status,'incomplete')
  self.assertTrue(any(f.code=='tool_missing' and f.category=='html'
                      and f.detail=='python3-html5lib' for f in report.findings))
  self.assertTrue(any(c['category']=='html' and c['status']=='unavailable'
                      for c in report.checks))
  self.assertFalse(any(c['category']=='html' and c['status']=='done'
                       for c in report.checks))
 def test_semantic_findings_and_local_paths(self):
  (self.root/'index.html').write_text('<html><head></head><body><h1 id="a">A</h1><h3 id="a">B</h3><img src="gone.png"><input><a href="#absent">link</a><a href="dynamic">route</a></body></html>')
  report=self.scan();codes={f.code for f in report.findings}
  self.assertTrue({'duplicate_id','alt_missing','label_missing','heading_jump','file_missing','fragment_missing','route_unknown'}<=codes)
 def test_php_syntax_checks_do_not_execute(self):
  if not shutil.which('php'):self.skipTest('PHP syntax checker is not installed')
  flag=self.root/'executed'
  (self.root/'safe.php').write_text('<?php file_put_contents('+repr(str(flag))+',"executed");')
  (self.root/'bad.php').write_text('<?php function broken( {')
  report=self.scan()
  self.assertFalse(flag.exists())
  self.assertIn('php',{f.category for f in report.findings if f.code=='syntax'})
 def test_javascript_syntax_checks_do_not_execute(self):
  if not shutil.which('node'):self.skipTest('Node.js syntax checker is not installed')
  flag=self.root/'executed'
  (self.root/'safe.js').write_text('require("fs").writeFileSync('+json.dumps(str(flag))+',"executed");')
  (self.root/'bad.js').write_text('const x = ;')
  report=self.scan()
  self.assertFalse(flag.exists())
  self.assertIn('javascript',{f.category for f in report.findings if f.code=='syntax'})
 def test_css_json_xml(self):
  (self.root/'bad.css').write_text('p { color red; }')
  (self.root/'bad.json').write_text('{"a":}')
  (self.root/'bad.xml').write_text('<x>')
  report=self.scan()
  self.assertEqual({f.category for f in report.findings if f.code=='syntax'},{'css','structured'})
 def test_sql_example_not_security_violation(self):
  (self.root/'index.html').write_text(VALID.decode().replace('Test</h1>',"SELECT * FROM pages WHERE '1'='1'</h1>"))
  self.assertFalse([f for f in self.scan().findings if f.category=='security'])
 def test_symlink_and_outside_root(self):
  (self.root/'loop').symlink_to(self.root,target_is_directory=True)
  (self.root/'index.html').write_text('<a href="../secret.txt">test</a>')
  self.assertTrue(any(f.code=='outside_root' for f in self.scan().findings))
 def test_cancel(self):
  event=threading.Event();event.set()
  report=Scanner('local',self.root,self.opts,cancel=event).run()
  self.assertEqual(report.status,'cancelled')
 def test_missing_tool_is_not_pass(self):
  (self.root/'test.php').write_text('<?php echo "ok";')
  with patch('modules.engine.shutil.which',return_value=None):report=self.scan()
  self.assertTrue(any(c['category']=='php' and c['status']=='unavailable' for c in report.checks))
 def test_exports_escape_untrusted_html(self):
  (self.root/'index.html').write_text('<div id="&lt;script&gt;alert(1)&lt;/script&gt;"></div>'*2)
  report=self.scan()
  save_report(report,self.root/'report.html')
  text=(self.root/'report.html').read_text()
  self.assertNotIn('<script>alert(1)</script>',text)
  save_report(report,self.root/'report.json')
  self.assertEqual(json.loads((self.root/'report.json').read_text())['schema_version'],1)
 def test_file_limit(self):
  for i in range(3):(self.root/f'{i}.html').write_bytes(VALID)
  self.opts['max_resources']=1
  self.assertTrue(any(f.code=='limit' for f in self.scan().findings))
 def test_css_url_missing(self):
  (self.root/'style.css').write_text('p { background: url("gone.png"); }')
  self.assertTrue(any(f.code=='file_missing' for f in self.scan().findings))
 def test_existing_basepath(self):
  (self.root/'assets').mkdir();(self.root/'assets/ok.html').write_bytes(VALID)
  (self.root/'index.html').write_text('<base href="assets/"><a href="ok.html#ok">OK</a>')
  self.assertFalse(any(f.code in ('file_missing','fragment_missing') for f in self.scan().findings))

class Handler(BaseHTTPRequestHandler):
 hits=[]
 def log_message(self,*args):pass
 def do_GET(self):
  type(self).hits.append(self.path)
  if self.path=='/robots.txt':body=b'User-agent: *\nDisallow: /private\n';code=200;mime='text/plain'
  elif self.path=='/':body=VALID.replace(b'</body>',b'<a href="/missing">bad</a><a href="/private">private</a><a href="/next#no">next</a><img src="/gone.png"></body>');code=200;mime='text/html'
  elif self.path=='/next':body=VALID;code=200;mime='text/html'
  elif self.path=='/private':body=b'secret';code=200;mime='text/plain'
  elif self.path=='/loop':self.send_response(302);self.send_header('Location','/loop');self.end_headers();return
  elif self.path=='/boundary':self.send_response(302);self.send_header('Location','http://example.org/');self.end_headers();return
  elif self.path=='/rate':self.send_response(429);self.send_header('Retry-After','60');self.end_headers();return
  else:body=b'not found';code=404;mime='text/plain'
  self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

class OnlineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.url='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def setUp(self):Handler.hits=[];self.opts=dict(DEFAULTS,categories=list(CATEGORIES),delay=.05,max_resources=100)
 def scan(self,path='/'):return Scanner('online',self.url+path,self.opts).run()
 def test_online_errors_robots_fragments(self):
  report=self.scan();codes={f.code for f in report.findings}
  self.assertEqual(report.status,'incomplete')
  self.assertTrue({'http_missing','robots_denied','fragment_missing'}<=codes)
  self.assertNotIn('/private',Handler.hits)
 def test_redirect_loop(self):self.assertTrue(any(f.code=='redirect_loop' for f in self.scan('/loop').findings))
 def test_cross_origin_redirect_is_not_followed(self):self.assertTrue(any(f.code=='redirect_boundary' for f in self.scan('/boundary').findings))
 def test_rate_limit(self):self.assertTrue(any(f.code=='rate_limit' for f in self.scan('/rate').findings))
 def test_budget(self):
  self.opts['max_resources']=2
  self.scan();self.assertLessEqual(len(Handler.hits),2)
 def test_invalid_scheme_and_credentials(self):
  for url in ('file:///etc/passwd','http://user:pass@example.org'):
   with self.assertRaises(ValueError):canonical(url)

class LanguageTests(unittest.TestCase):
 def test_keys_and_placeholders(self):
  root=Path(__file__).resolve().parent.parent
  en=json.loads((root/'lang/en.json').read_text());de=json.loads((root/'lang/de.json').read_text())
  self.assertEqual(set(en),set(de))
  from modules.i18n import fields
  for key in en:self.assertEqual(fields(en[key]),fields(de[key]),key)
 def test_pack_validation_and_sanitization(self):
  code,strings,html=validate_pack({'program_id':'checkweb','code':'fr','strings':{'start':'Démarrer'},'help_html':'<h1>Test</h1><script>alert(1)</script><a href="https://evil.invalid/">X</a>'})
  self.assertNotIn('script',html);self.assertNotIn('evil.invalid',html)
  self.assertEqual(code,'fr')
 def test_traversal_and_placeholder_rejected(self):
  for pack in ({'program_id':'checkweb','code':'../de','strings':{'start':'X'},'help_html':'X'},{'program_id':'checkweb','code':'fr','strings':{'summary':'wrong'},'help_html':'X'}):
   with self.assertRaises(ValueError):validate_pack(pack)
 def test_missing_language_fallback(self):self.assertEqual(Strings('xx')('start'),'Start scan')


class ExtraBehaviorTests(unittest.TestCase):
 def test_language_install_and_protection(self):
  import os
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_CONFIG_HOME':folder}):
   with patch('modules.languages.config_dir',return_value=Path(folder)):
    pack={'program_id':'checkweb','code':'fr','strings':{'start':'Démarrer'},'help_html':'<html><h1>Aide</h1></html>'}
    self.assertEqual(install_pack(pack),'fr')
    with self.assertRaises(FileExistsError):install_pack(pack)
    self.assertEqual(json.loads((Path(folder)/'languages/fr/strings.json').read_text())['start'],'Démarrer')
 def test_arabic_help_direction(self):
  _,_,html=validate_pack({'program_id':'checkweb','code':'ar','strings':{'start':'ابدأ'},'help_html':'<html dir="rtl"><p>مساعدة</p></html>'})
  self.assertIn('dir="rtl"',html)
 def test_invalid_language_setting_falls_back(self):
  self.assertEqual(Strings('../../etc').code,'en')
 def test_subprocess_timeout(self):
  import sys
  scanner=Scanner('local','.',dict(DEFAULTS,timeout=.05))
  with self.assertRaises(TimeoutError):scanner.command([sys.executable,'-c','import time;time.sleep(10)'],b'')
 def test_css_import_reference(self):
  with tempfile.TemporaryDirectory() as folder:
   Path(folder,'style.css').write_text('@import "absent.css";')
   report=Scanner('local',folder,dict(DEFAULTS,external_links=False,categories=['css','links'])).run()
   self.assertTrue(any(f.code=='file_missing' for f in report.findings))

if __name__=='__main__':unittest.main()
