import json
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from requests.structures import CaseInsensitiveDict

from modules.engine import Scanner,Skipped,BODY_CACHE_LIMIT
from modules.jsrefs import parse,requests_in,ParserLimit
from modules.model import DEFAULTS
from prerequisites import require_node_acorn


class RobotRedirectHandler(BaseHTTPRequestHandler):
    paths=[]
    def log_message(self,*args):pass
    def do_GET(self):
        type(self).paths.append(self.path)
        if self.path=='/robots.txt':body=b'User-agent: *\nDisallow: /private\n';status=200
        elif self.path=='/start':body=b'';status=302;self.send_response(status);self.send_header('Location','/private');self.send_header('Content-Length','0');self.end_headers();return
        else:body=b'<html><title>ok</title></html>';status=200
        self.send_response(status)
        if self.path=='/robots.txt':self.send_header('cOnTeNt-TyPe','text/plain')
        else:self.send_header('CONTENT-TYPE','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),RobotRedirectHandler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()

    def test_robots_rechecked_before_redirect_target_get(self):
        RobotRedirectHandler.paths=[]
        scanner=Scanner('online',self.base+'/start',dict(DEFAULTS,categories=['links'],delay=0,timeout=2))
        try:
            with self.assertRaises(Skipped):scanner.fetch(self.base+'/start',source='source.html',line=17)
            self.assertIn('/robots.txt',RobotRedirectHandler.paths)
            self.assertIn('/start',RobotRedirectHandler.paths)
            self.assertNotIn('/private',RobotRedirectHandler.paths)
            finding=next(f for f in scanner.report.findings if f.code=='robots_denied')
            self.assertEqual((finding.destination,finding.line),(self.base+'/private',17))
        finally:scanner.session.close()

    def test_header_casing_and_html_mime_are_case_insensitive(self):
        for name in ('Content-Type','content-type','CONTENT-TYPE','cOnTeNt-TyPe'):
            self.assertEqual(Scanner.extension('https://example.invalid/no-suffix',{name:'text/html'}),'.html')
            scanner=Scanner('online','https://example.invalid/',dict(DEFAULTS,categories=['security']))
            headers={name:'text/html; charset=iso-8859-1','CONTENT-SECURITY-POLICY':'default-src \'self\'','x-content-type-options':'nosniff'}
            self.assertEqual(scanner.decode('caf\xe9'.encode('latin-1'),'page',headers),'café')
            scanner.html('<html><head></head><body></body></html>','https://example.invalid/',headers)
            self.assertFalse(any(f.code in ('csp_missing','nosniff_missing') for f in scanner.report.findings))
            scanner.session.close()

    def test_decode_prefers_case_insensitive_explicit_charset(self):
        scanner=Scanner('online','https://example.invalid/',dict(DEFAULTS,categories=['security']))
        payload='café'.encode('iso-8859-1')
        for name in ('Content-Type','content-type','CONTENT-TYPE','cOnTeNt-TyPe'):
            for make_headers in (dict,CaseInsensitiveDict):
                headers=make_headers({name:'text/html; charset=iso-8859-1'})
                with patch('modules.engine.UnicodeDammit',side_effect=AssertionError('automatic detection must not override an explicit charset')):
                    self.assertEqual(scanner.decode(payload,'page',headers),'café')
        self.assertEqual(scanner.decode('café'.encode('utf-8'),'page',{'CONTENT-TYPE':'text/html; charset=utf-8'}),'café')
        scanner.session.close()

    def test_parser_distinguishes_regex_division_and_literal_calls(self):
        require_node_acorn()
        source="""const ghost=/fetch('ghost.json')/; const n=12 / 3;
// fetch('/comment.json')
const text=\"fetch('/string.json')\"; const tpl=`fetch('/template.json')`;
fetch('./real.json'); fetch(`./static-template.json`); fetch('./head.json',{method:'HEAD'}); fetch('./post.json',{method:'POST'});
fetch('./dynamic/'+name); import('./dynamic.js'); import('./dynamic/'+name); import './static-module.js'; export { value } from './re-export.js';
const xhr=new XMLHttpRequest(); xhr.open('GET','./xhr.json',true);
function f(fetch){fetch('./shadow.json')}"""
        result=parse(source,'module')
        self.assertTrue(result['ok'])
        self.assertEqual([x['url'] for x in result['refs']], ['./real.json','./static-template.json','./head.json','./dynamic.js','./static-module.js','./re-export.js','./xhr.json'])
        self.assertEqual([value for value,_ in requests_in(source,'module')], ['./real.json','./static-template.json','./head.json','./dynamic.js','./static-module.js','./re-export.js','./xhr.json'])

    def test_parser_modes_syntax_and_bounds(self):
        require_node_acorn()
        module=parse('const a=1; export {a};','auto')
        self.assertTrue(module['ok']);self.assertEqual(module['mode'],'module');self.assertTrue(module['ambiguous'])
        self.assertIn('Unexpected token',parse('const value = ;','script')['error']['message'])
        self.assertTrue(parse("const f=()=>fetch?.('/ok'); const x=await import('./x.js')",'module')['ok'])
        with self.assertRaises(ParserLimit):parse('x'*1_000_001,'script')
        with patch('modules.jsrefs.PARSER_TIMEOUT',-1):
            with self.assertRaises(ParserLimit):parse('const a=1;','script')

    def test_local_module_script_context_reaches_external_file(self):
        require_node_acorn()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'index.html').write_text('<script type="module" src="app.js"></script>')
            (root/'app.js').write_text('const a=1; export {a};')
            report=Scanner('local',folder,dict(DEFAULTS,categories=['javascript','links'],external_links=False)).run()
            self.assertFalse(any(f.code=='syntax' for f in report.findings))
            self.assertFalse(any(f.code=='javascript_context_unclear' for f in report.findings))

    def test_links_only_marks_dynamic_or_unavailable_javascript_unchecked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'app.js').write_text("fetch('/api/'+name);")
            report=Scanner('local',folder,dict(DEFAULTS,categories=['links'],external_links=False)).run()
            self.assertEqual(report.status,'incomplete')
            self.assertTrue(any(c['category']=='links' and c['status']=='not_checked' for c in report.checks))
            self.assertNotIn('missing_checks',report.incomplete_reasons)
            self.assertIn('inconclusive_checks',report.incomplete_reasons)
            with patch('modules.jsrefs.shutil.which',return_value=None):
                missing=Scanner('local',folder,dict(DEFAULTS,categories=['links'],external_links=False)).run()
            self.assertEqual(missing.status,'incomplete')
            self.assertTrue(any(c['category']=='links' and c['status']=='unavailable' for c in missing.checks))
            self.assertIn('missing_checks',missing.incomplete_reasons)

    def test_body_cache_total_cap_is_reported_without_storing_more_bodies(self):
        RobotRedirectHandler.paths=[]
        scanner=Scanner('online',self.base+'/start',dict(DEFAULTS,categories=['links'],delay=0,timeout=2,robots=False))
        try:
            with patch('modules.engine.BODY_CACHE_LIMIT',1):
                scanner.fetch(self.base+'/start')
                self.assertEqual(scanner.cache_body_bytes,0)
                self.assertEqual(scanner.report.limits['body_cache_bytes'],1)
                self.assertIn('body_cache',scanner.report.incomplete_reasons)
        finally:scanner.session.close()

    def test_cancel_escalates_when_child_ignores_sigint(self):
        from modules.scanprocess import run_interruptible
        for ready in (False,True):
            event=threading.Event()
            code="import signal,time;signal.signal(signal.SIGINT,signal.SIG_IGN);"+('print(\"{\\\"kind\\\":\\\"ready\\\"}\",flush=True);' if ready else '')+"time.sleep(30)"
            real_popen=subprocess.Popen
            def fake_popen(*args,**kwargs):
                return real_popen([sys.executable,'-c',code],**kwargs)
            timer=threading.Timer(.12,event.set);timer.start();started=time.monotonic()
            try:
                with patch('modules.scanprocess.subprocess.Popen',side_effect=fake_popen):
                    report=run_interruptible('local','.',dict(DEFAULTS,categories=['links']),lambda *a:None,event)
                self.assertEqual(report.status,'cancelled')
                self.assertIn('forced_process_termination',report.incomplete_reasons)
                self.assertLess(time.monotonic()-started,3)
            finally:timer.cancel();timer.join()

    def test_cancel_escalates_to_kill_without_child_output(self):
        from modules.scanprocess import run_interruptible
        event=threading.Event();code="import signal,time;signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
        real_popen=subprocess.Popen
        def fake_popen(*args,**kwargs):return real_popen([sys.executable,'-c',code],**kwargs)
        timer=threading.Timer(.12,event.set);timer.start();started=time.monotonic()
        try:
            with patch('modules.scanprocess.subprocess.Popen',side_effect=fake_popen):
                report=run_interruptible('local','.',dict(DEFAULTS,categories=['links']),lambda *a:None,event)
            self.assertEqual(report.status,'cancelled')
            self.assertIn('forced_process_termination',report.incomplete_reasons)
            self.assertLess(time.monotonic()-started,3)
        finally:timer.cancel();timer.join()


if __name__=='__main__':unittest.main()
