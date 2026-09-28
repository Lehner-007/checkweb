"""HTTP classification, skipped coverage and grouped report regressions."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
import requests
from bs4 import BeautifulSoup
from modules.engine import Scanner
from modules.model import DEFAULTS,Report,Finding
from modules.reports import html_report,group_findings,finding_section,save_report

class Handler(BaseHTTPRequestHandler):
    hits=[]
    def log_message(self,*args):pass
    def do_GET(self):
        type(self).hits.append(self.path)
        status=200;headers={};body=b''
        if self.path=='/robots.txt':body=b'User-agent: *\nDisallow: /private\n'
        elif self.path=='/redirect':status=302;headers['Location']='/ok'
        elif self.path=='/many':body=(''.join(f'<a href="/status/403?n={n}">x</a>' for n in range(30))).encode()
        elif self.path=='/links':body=(''.join(f'<a href="/status/{n}">{n}</a>' for n in (200,301,401,403,404,410,500,503))).encode()
        elif self.path.startswith('/status/'):
            status=int(self.path.split('/')[-1].split('?')[0])
            if status==429:headers['Retry-After']='60'
        else:body=b'<!doctype html><html><head><title>OK</title></head><body><p>OK</p></body></html>'
        self.send_response(status)
        self.send_header('Content-Type','text/html')
        self.send_header('Content-Length',str(len(body)))
        for k,v in headers.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        Handler.hits=[]
        self.opts=dict(DEFAULTS,categories=['links'],robots=False,delay=0,max_resources=100)
    def scan(self,path,**opts):return Scanner('online',self.url+path,dict(self.opts,**opts)).run()
    def test_http_status_matrix(self):
        expected={200:None,204:None,301:'redirect_pending',401:'http_auth',403:'http_forbidden',404:'http_missing',410:'http_missing',429:'rate_limit',500:'http_server',503:'http_server'}
        for status,code in expected.items():
            with self.subTest(status=status):
                report=self.scan('/status/'+str(status))
                self.assertEqual([f.code for f in report.findings],[] if code is None else [code])
                if code:
                    f=report.findings[0]
                    self.assertEqual(f.severity,'error' if status in (404,410) else 'warning' if status>=500 else 'info')
                    self.assertEqual(finding_section(f),'errors' if status in (404,410) else 'redirects' if status==301 else 'manual' if status in (401,403) else 'indeterminate')
                if status in (401,403,429,500,503,301):self.assertTrue(any(c['status']=='not_checked' for c in report.checks))
    def test_referring_page_kept_for_status_findings(self):
        report=self.scan('/links',max_depth=0)
        for code in ('http_auth','http_forbidden','http_missing','http_server'):
            self.assertTrue(any(f.code==code and f.target==self.url+'/links' and '/status/' in f.detail for f in report.findings))
    def test_local_external_links_use_same_classification(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'index.html').write_text(f'<a href="{self.url}/status/403">x</a><a href="{self.url}/status/404">y</a>')
            report=Scanner('local',folder,self.opts).run()
            self.assertEqual({f.code for f in report.findings},{'http_forbidden','http_missing'})
    def test_normal_redirect_is_informational(self):
        report=self.scan('/redirect')
        self.assertEqual([f.code for f in report.findings],['redirect'])
        self.assertEqual(report.findings[0].severity,'info')
        self.assertIn('/ok',Handler.hits)
    def test_robots_denial_is_unchecked_not_error(self):
        report=self.scan('/private',robots=True)
        self.assertNotIn('/private',Handler.hits)
        self.assertEqual(report.findings[0].code,'robots_denied')
        self.assertEqual(finding_section(report.findings[0]),'indeterminate')
        self.assertTrue(any(c['status']=='not_checked' for c in report.checks))
    def test_timeout_is_inconclusive(self):
        with patch('requests.Session.get',side_effect=requests.Timeout('test')):report=self.scan('/ok')
        self.assertEqual(report.findings[0].code,'http_timeout')
        self.assertEqual(finding_section(report.findings[0]),'indeterminate')
    def test_robots_failure_is_not_claimed_as_disallow(self):
        with patch('requests.Session.get',side_effect=requests.Timeout('test')):report=self.scan('/ok',robots=True)
        self.assertIn('robots_unavailable',{f.code for f in report.findings})
        self.assertNotIn('robots_denied',{f.code for f in report.findings})
    def test_many_budget_hits_make_one_incomplete_notice(self):
        report=self.scan('/many',max_resources=2)
        self.assertEqual(report.status,'incomplete')
        self.assertEqual(report.limits,{'max_resources':2})
        self.assertEqual(sum(f.code=='limit' for f in report.findings),1)
        self.assertEqual(len(Handler.hits),2)
    def test_budget_during_redirect_is_not_silent(self):
        report=self.scan('/redirect',max_resources=1)
        self.assertEqual(report.status,'incomplete')
        self.assertEqual(report.limits,{'max_resources':1})
    def test_budget_consumed_by_robots_is_not_silent(self):
        report=self.scan('/ok',robots=True,max_resources=1)
        self.assertEqual(report.status,'incomplete')
        self.assertEqual(Handler.hits,['/robots.txt'])
    def test_page_limit_is_incomplete(self):
        report=self.scan('/links',max_pages=1)
        self.assertEqual(report.status,'incomplete')
        self.assertEqual(report.limits,{'max_pages':1})

class ReportTests(unittest.TestCase):
    def report(self):
        r=Report('online','https://example.invalid/',[],status='incomplete',limits={'max_resources':300})
        r.findings=[Finding('info','links',f'https://example.invalid/{i}','redirect','https://example.invalid/end') for i in range(50)]
        r.findings += [Finding('error','links','<script>alert(1)</script>','http_missing','HTTP 404'),Finding('info','links','/private','robots_denied'),Finding('info','links','/blocked','http_forbidden','HTTP 403'),Finding('info','system',r.target,'limit','max_resources')]
        r.checks=[dict(target='/private',category='links',status='not_checked',tool='requests')]
        return r
    def test_grouping_keeps_all_sources(self):
        groups=group_findings(self.report().findings)
        redirects=[g for g in groups if g[0].code=='redirect']
        self.assertEqual(len(redirects),1);self.assertEqual(len(redirects[0]),50)
    def test_report_order_limit_and_escaping(self):
        soup=BeautifulSoup(html_report(self.report(),'de'),'html.parser')
        self.assertEqual([h.get_text() for h in soup.select('h2')],['Zusammenfassung','Fehler der eigenen Webseite / Prüfung','Defekte externe Links / Ressourcen','Manuell zu prüfende Ergebnisse','Nicht automatisch bestimmbar – manuell prüfen','Warnungen','Hinweise / Optimierungen','Nicht geprüfte Bereiche','Weiterleitungen','Technische Details'])
        self.assertFalse(soup.find_all('script'))
        self.assertEqual(len(soup.select('.incomplete')),1)
        self.assertEqual(soup.get_text().count('Ressourcenlimit erreicht: 300'),1)
        self.assertEqual(sum('Normale Weiterleitung' in h.get_text() for h in soup.select('h3')),1)
        self.assertIn('50 Fundstellen',soup.get_text())
        self.assertIn('Nicht geprüft / Ergebnis unbestimmt',soup.get_text())
    def test_json_remains_lossless(self):
        r=self.report()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.json';save_report(r,path)
            data=json.loads(path.read_text())
            self.assertEqual(len(data['findings']),len(r.findings));self.assertEqual(data['limits'],r.limits)
    def test_english_report_has_translated_sections(self):
        soup=BeautifulSoup(html_report(self.report(),'en'),'html.parser')
        self.assertIn('Results requiring manual review',[h.get_text() for h in soup.select('h2')])
        self.assertIn('Resource limit reached: 300',soup.get_text())
