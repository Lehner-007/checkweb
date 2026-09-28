import unittest
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from bs4 import BeautifulSoup
import requests
from urllib3.exceptions import ReadTimeoutError
import test_http_reports as fixtures
from modules.engine import Scanner
from modules.model import DEFAULTS,Finding,Report
from modules.reports import html_report,format_duration,format_timestamp

class Handler(fixtures.Handler):
    def do_GET(self):
        if self.path=='/chain':
            self.send_response(302);self.send_header('Location','/redirect');self.end_headers();return
        if self.path!='/summary':return super().do_GET()
        type(self).hits.append(self.path)
        body=(f'<html><body>\n<a href="/status/200">ok</a>\n<a href="/status/200#part">same</a>\n<a href="/status/404">missing</a>\n<a href="http://localhost:{self.server.server_port}/status/403">external</a></body></html>').encode()
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def scan(self,**opts):
        return Scanner('online',self.url+'/summary',dict(DEFAULTS,categories=['links'],robots=False,delay=0,max_depth=0,**opts)).run()
    def test_counts_are_unique_and_add_up(self):
        r=self.scan(external_links=False)
        self.assertEqual(r.resource_counts,dict(found=4,checked=3,unchecked=1,analyzed=2,http_requests=4))
        self.assertEqual(r.status,'incomplete')
        self.assertEqual(len(r.resource_details),4)
        self.assertGreater(r.duration_seconds,0)
    def test_budget_discovers_remaining_references(self):
        r=self.scan(max_resources=1)
        self.assertEqual(r.resource_counts['found'],4)
        self.assertEqual(r.resource_counts['checked'],1)
        self.assertEqual(r.resource_counts['unchecked'],3)
        self.assertEqual(r.resource_counts['http_requests'],1)
        self.assertEqual(sum(f.code=='limit' and f.detail=='max_resources' for f in r.findings),1)
    def test_http_context_and_external_scope(self):
        r=self.scan(external_links=True)
        f=next(f for f in r.findings if f.code=='http_forbidden')
        self.assertEqual(f.http_status,403)
        self.assertEqual(f.scope,'external')
        self.assertEqual(f.target,self.url+'/summary')
        self.assertIn('localhost:',f.destination)
        self.assertGreater(f.line,0)
        self.assertEqual(next(f for f in r.findings if f.code=='http_missing').scope,'internal')
        html=BeautifulSoup(html_report(r,'de'),'html.parser')
        self.assertIn('fremden Domain',html.get_text())
        self.assertIn('nicht vollständig',html.get_text())
    def test_completed_redirect_chain_has_no_pending_resources(self):
        r=Scanner('online',self.url+'/chain',dict(DEFAULTS,categories=['links'],robots=False,delay=0)).run()
        self.assertEqual(r.status,'complete')
        self.assertEqual(r.resource_counts['found'],3)
        self.assertEqual(r.resource_counts['unchecked'],0)
    def test_zero_depth_is_unlimited(self):
        r=self.scan(external_links=False)
        self.assertNotIn('max_depth',r.limits)
        self.assertEqual(r.resource_counts['analyzed'],2)
    def test_missing_tool_not_counted_as_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'a.php').write_text('<?php echo "test";')
            with patch('modules.engine.shutil.which',return_value=None):
                r=Scanner('local',tmp,dict(DEFAULTS,categories=['php'],external_links=False)).run()
            self.assertEqual(r.resource_counts['found'],1)
            self.assertEqual(r.resource_counts['checked'],0)
            self.assertEqual(r.status,'incomplete')
    def test_nested_readtimeout_classified(self):
        error=requests.ConnectionError(ReadTimeoutError(None,'/','timed out'))
        with patch('requests.Session.get',side_effect=error):r=self.scan()
        self.assertEqual(r.findings[0].code,'http_timeout')
        self.assertEqual(r.resource_counts['checked'],0)
    def test_summary_date_duration_and_counts(self):
        r=self.scan(external_links=False)
        r.started='2026-09-27T14:09:08+00:00';r.finished='2026-09-27T14:10:26+00:00';r.duration_seconds=78
        self.assertEqual(format_duration(r),'1 min 18 s')
        self.assertTrue(format_timestamp(r.started).startswith('27.09.2026'))
        text=BeautifulSoup(html_report(r,'de'),'html.parser').get_text(' ',strip=True)
        self.assertIn('Bekannte eindeutige Ziele 4',text)
        self.assertIn('Befundanzahl je Ergebnisgruppe',text)
        self.assertIn('1 min 18 s',text)
    def test_all_error_sources_visible_without_expanding(self):
        r=Report('online','https://example.org',[])
        r.findings=[Finding('error','links','first-page','http_missing',line=10,destination='https://example.org/a',http_status=404,scope='internal'),Finding('error','links','second-page','http_missing',line=20,destination='https://example.org/b',http_status=410,scope='internal')]
        soup=BeautifulSoup(html_report(r,'en'),'html.parser')
        for details in soup.select('details'):details.decompose()
        text=soup.get_text()
        self.assertIn('first-page',text);self.assertIn('second-page',text);self.assertIn('410',text)
