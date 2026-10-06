"""Additional diagnostics: bounded requests and honest result classification."""
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import requests
from modules.engine import Scanner
from modules.model import DEFAULTS
from modules.reports import html_report

class Handler(BaseHTTPRequestHandler):
    hits=[]
    def log_message(self,*args):pass
    def do_GET(self):
        self.hits.append(self.path)
        if self.path=='/redirect':
            self.send_response(302);self.send_header('Location','/');self.end_headers();return
        status=200
        body=b'<html><head><title>OK</title><link rel="canonical" href="/dead"></head><body>hello</body></html>'
        if self.path=='/robots.txt':body=b'User-agent: *\nDisallow: /private\n'
        elif self.path=='/sitemap.xml':body=(f'<urlset><url><loc>http://127.0.0.1:{self.server.server_port}/private</loc></url></urlset>').encode()
        elif self.path=='/dead':status=404;body=b'Not found'
        elif self.path.startswith('/checkweb-not-found-'):body=b'Page not found 404'
        self.send_response(status);self.send_header('Content-Length',str(len(body)));self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(body)

class DiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def scanner(self,**options):return Scanner('online',self.url,dict(DEFAULTS,categories=['website'],delay=0,**options))
    def test_soft404_canonical_sitemap_and_tls_are_separate(self):
        report=self.scanner(robots=True).run()
        codes={f.code for f in report.findings}
        self.assertTrue({'soft_404','canonical_unreachable','sitemap_robots','tls_error'}<=codes,codes)
        self.assertEqual(report.status,'incomplete')
        self.assertIn('Zusätzliche Netzwerkprüfungen',html_report(report,'de'))
        self.assertTrue(any(t['purpose']=='error_page' and t['http_status']==200 for t in report.network_tests))
    def test_request_budget_and_disabled_category(self):
        Handler.hits=[]
        report=self.scanner(robots=False,max_resources=2).run()
        self.assertLessEqual(report.resource_counts['http_requests'],2)
        self.assertEqual(report.status,'incomplete')
        report=Scanner('online',self.url,dict(DEFAULTS,categories=['links'],robots=False,delay=0)).run()
        self.assertEqual(report.network_tests,[])
    def test_failure_types_follow_exception_causes(self):
        dns=requests.ConnectionError('lookup');dns.__cause__=socket.gaierror(-2,'unknown')
        for error,code in [(dns,'dns_error'),(requests.ConnectionError('refused'),'connection_error'),(requests.exceptions.SSLError('bad cert'),'tls_error'),(requests.Timeout(),'http_timeout')]:
            with self.subTest(code=code),patch('requests.Session.get',side_effect=error):
                report=Scanner('online',self.url,dict(DEFAULTS,categories=['links'],robots=False)).run()
                self.assertIn(code,{f.code for f in report.findings})
                self.assertEqual(report.status,'incomplete')
    def test_cancelled_does_not_claim_not_applicable(self):
        scan=self.scanner();scan.cancel.set();report=scan.run()
        self.assertEqual(report.status,'cancelled')
        self.assertTrue(any(c['category']=='website' and c['status']=='not_checked' for c in report.checks))

    def test_cached_redirect_chain_is_retained(self):
        scanner=Scanner('online',self.url+'redirect',dict(DEFAULTS,categories=['website'],robots=False,delay=0))
        report=scanner.run()
        variant=next(t for t in report.network_tests if t['purpose']=='address_variant' and t['target']==self.url+'redirect')
        self.assertEqual(variant['chain'][0]['target'],self.url+'redirect')
        self.assertEqual(variant['chain'][0]['destination'],self.url)
        self.assertTrue(any(t['status']=='not_checked' and 'tls_error' in t['reasons'] for t in report.network_tests))
