"""Input regressions without internet access."""
import unittest
from modules.engine import canonical,normalize_url_input,Scanner
from modules.model import DEFAULTS

class URLInputTests(unittest.TestCase):
    def test_https_default(self):
        for value,expected in [('example.org','https://example.org/'),(' example.org/a?q=1 ','https://example.org/a?q=1'),('//example.org/a','https://example.org/a'),('localhost:8443','https://localhost:8443/')]:
            with self.subTest(value=value):self.assertEqual(canonical(normalize_url_input(value)),expected)
    def test_explicit_http_is_preserved(self):
        self.assertEqual(canonical(normalize_url_input('http://localhost:8000/a')),'http://localhost:8000/a')
    def test_invalid_or_unsafe_address_is_rejected(self):
        for value in ('https://','ftp://example.org','javascript:alert(1)','https://user:pass@example.org'):
            with self.subTest(value=value),self.assertRaises(ValueError):canonical(normalize_url_input(value))
    def test_cli_scanner_uses_same_default(self):
        scanner=Scanner('online','example.org',DEFAULTS)
        try:self.assertEqual(scanner.target,'https://example.org')
        finally:scanner.session.close()
