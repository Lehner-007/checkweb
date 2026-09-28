"""Manual review requirements: limits, resources, log editing and scope."""
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from bs4 import BeautifulSoup
from modules.engine import Scanner,Cancelled
from modules.jsrefs import requests_in
from modules.logfile import read_log,save_log,LogChangedError
from modules.model import DEFAULTS,settings
from modules.reports import finding_section,html_report

class Handler(BaseHTTPRequestHandler):
    hits=[]
    def log_message(self,*args):pass
    def do_GET(self):
        type(self).hits.append(self.path)
        status=200;mime='text/html';body=b''
        if self.path=='/pages/start':
            body=(f'''<!doctype html><html><head><link rel="stylesheet" href="../css/main.css"></head><body>
<a href="/pages/second">Next</a>
<a href="http://localhost:{self.server.server_port}/missing">GNOME &amp; link</a>
<a href="http://localhost:{self.server.server_port}/forbidden">Browser review</a>
<script src="../js/app.js"></script>
<img src="../images/missing.png" alt="Logo"></body></html>''').encode()
        elif self.path=='/pages/second':body=b'<a href="/pages/third">Third</a>'
        elif self.path=='/pages/third':body=b'<a href="/pages/start">Cycle</a>'
        elif self.path=='/css/main.css':mime='text/css';body=b'@import "nested/theme.css"; @font-face {font-family:test;src:url("../fonts/test.woff2")} '
        elif self.path=='/css/nested/theme.css':mime='text/css';body=b'@import "../main.css"; p {background:url("../../images/other.png")} '
        elif self.path=='/js/app.js':mime='text/javascript';body=b'fetch("./data.json"); const x=new XMLHttpRequest(); x.open("GET", "../api/info.json"); fetch("/post", {method:"POST"});'
        elif self.path in ('/pages/data.json','/api/info.json'):mime='application/json';body=b'{}'
        elif self.path=='/fonts/test.woff2':mime='font/woff2';body=b'test-font'
        elif self.path=='/forbidden':status=403
        elif self.path=='/blocked':time.sleep(3);body=b'late'
        elif self.path=='/slow':time.sleep(.15);body=b'<p>slow</p>'
        else:status=404
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except BrokenPipeError:pass

class ManualReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):Handler.hits=[]
    def scan(self,path='/pages/start',**changes):
        return Scanner('online',self.url+path,dict(DEFAULTS,categories=['links','css'],robots=False,delay=0,max_pages=0,max_depth=0,max_resources=0,timeout=0,**changes)).run()
    def test_unlimited_scans_all_pages_and_nested_resources(self):
        r=self.scan()
        self.assertNotEqual(r.status,'failed',[f.detail for f in r.findings])
        self.assertEqual(r.limits,{})
        for path in ('/pages/third','/css/nested/theme.css','/fonts/test.woff2','/images/other.png','/pages/data.json','/api/info.json'):
            self.assertIn(path,Handler.hits)
        self.assertNotIn('/post',Handler.hits)
        self.assertLess(len(Handler.hits),30) # Cycles terminate even without limits.
        rows={x['target']:x for x in r.resource_details}
        font=rows[self.url+'/fonts/test.woff2']
        self.assertEqual(font['type'],'font');self.assertEqual(font['http_status'],200)
        self.assertEqual(font['references'][0]['source'],self.url+'/css/main.css')
        self.assertEqual(rows[self.url+'/pages/data.json']['type'],'fetch')
        self.assertEqual(rows[self.url+'/js/app.js']['type'],'javascript')
        self.assertEqual(rows[self.url+'/images/other.png']['references'][0]['source'],self.url+'/css/nested/theme.css')
    def test_internal_external_errors_and_manual_distinct(self):
        r=self.scan()
        internal=[f for f in r.findings if finding_section(f)=='errors']
        external=[f for f in r.findings if finding_section(f)=='external_errors']
        self.assertTrue(internal);self.assertEqual(len(external),1)
        self.assertEqual(external[0].http_status,404)
        self.assertEqual(external[0].link_text,'GNOME & link')
        self.assertEqual(external[0].line,3)
        manual=[f for f in r.findings if finding_section(f)=='manual']
        self.assertEqual(len(manual),1);self.assertEqual(manual[0].http_status,403)
        soup=BeautifulSoup(html_report(r,'de'),'html.parser')
        headings=[x.get_text() for x in soup.select('h2')]
        self.assertLess(headings.index('Fehler der eigenen Webseite / Prüfung'),headings.index('Defekte externe Links / Ressourcen'))
        self.assertIn('GNOME & link',soup.get_text());self.assertIn('Schriften',soup.get_text())
    def test_positive_depth_still_limits(self):
        opts=dict(DEFAULTS,categories=['links'],max_pages=0,max_depth=1,max_resources=0,timeout=0,robots=False,delay=0)
        r=Scanner('online',self.url+'/pages/second',opts).run()
        self.assertEqual(r.limits,{'max_depth':1})
    def test_zero_timeout_accepts_slow_response(self):
        r=self.scan('/slow')
        self.assertEqual(r.status,'complete');self.assertFalse(r.findings)
    def test_zero_tool_timeout_and_cancellation(self):
        scanner=Scanner('local','.',dict(DEFAULTS,timeout=0))
        rc,_=scanner.command([sys.executable,'-c','import time;time.sleep(.1)'],b'')
        self.assertEqual(rc,0)
        timer=threading.Timer(.1,scanner.cancel.set);timer.start()
        try:
            with self.assertRaises(Cancelled):scanner.command([sys.executable,'-c','import time;time.sleep(30)'],b'')
        finally:timer.join();scanner.session.close()
    def test_local_relative_paths_and_fonts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ('pages','css','js','fonts'):(root/folder).mkdir()
            (root/'pages/index.html').write_text('<link rel="stylesheet" href="../css/site.css"><script src="../js/site.js"></script>')
            (root/'css/site.css').write_text('@font-face {src:url("../fonts/test.woff2")}')
            (root/'fonts/test.woff2').write_bytes(b'test')
            (root/'js/site.js').write_text('fetch("./data.json");')
            (root/'pages/data.json').write_text('{}')
            r=Scanner('local',tmp,dict(DEFAULTS,categories=['links','css'],max_resources=0,external_links=False)).run()
            self.assertEqual(r.status,'complete',[(f.code,f.detail) for f in r.findings])
            self.assertFalse([f for f in r.findings if f.code=='file_missing'])
            font=next(x for x in r.resource_details if x['type']=='font')
            self.assertTrue(font['checked']);self.assertTrue(font['references'])
    def test_static_js_ignores_comments_strings_and_post(self):
        text='''// fetch('/comment')
        const s="fetch('/string')"; /*fetch('/block')*/
        fetch('/ok'); fetch('/post', {method:'POST'});
        fetch(`/dynamic/${x}`); xhr.open('POST','/no'); xhr.open('GET','/yes');'''
        self.assertEqual([v for v,_ in requests_in(text)],['/ok','/yes'])
    def test_unlimited_network_cancel_returns_partial_report(self):
        from modules.scanprocess import run_interruptible
        event=threading.Event()
        def cancel_when_connected():
            deadline=time.monotonic()+5
            while '/blocked' not in Handler.hits and time.monotonic()<deadline:time.sleep(.01)
            event.set()
        thread=threading.Thread(target=cancel_when_connected);thread.start()
        started=time.monotonic()
        r=run_interruptible('online',self.url+'/blocked',dict(DEFAULTS,robots=False,timeout=0,categories=['links']),lambda *args:None,event)
        thread.join()
        self.assertEqual(r.status,'cancelled')
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual(r.resource_counts['unchecked'],1)
    def test_saved_zero_values_survive_loading(self):
        with tempfile.TemporaryDirectory() as tmp,patch('modules.model.config_dir',return_value=Path(tmp)):
            Path(tmp,'settings.json').write_text(json.dumps(dict(DEFAULTS,max_pages=0,max_depth=0,max_resources=0,timeout=0)))
            loaded=settings()
            self.assertEqual([loaded[k] for k in ('max_pages','max_depth','max_resources','timeout')],[0]*4)

class LogTests(unittest.TestCase):
    def test_save_preserves_logger_and_rejects_concurrent_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'checkweb.log'
            handler=RotatingFileHandler(path,maxBytes=1000,backupCount=1,encoding='utf-8')
            logger=logging.getLogger('checkweb-test-log');logger.setLevel(logging.WARNING);logger.addHandler(handler)
            try:
                logger.warning('before')
                old=read_log(path)
                saved=save_log(path,'edited\n',old)
                logger.warning('after')
                self.assertEqual(read_log(path),b'edited\nafter\n')
                with self.assertRaises(LogChangedError):save_log(path,'lost\n',saved)
                self.assertIn(b'after',read_log(path))
            finally:logger.removeHandler(handler);handler.close()
    def test_missing_log_can_be_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'logs/checkweb.log'
            self.assertEqual(read_log(path),b'')
            save_log(path,'new',b'');self.assertEqual(read_log(path),b'new')
