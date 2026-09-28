"""Scan data, settings, and bounded tool discovery."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import importlib.util
import importlib.metadata
import subprocess
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

PROGRAM_ID = 'checkweb'
ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
CATEGORIES = ('html', 'css', 'javascript', 'php', 'structured', 'links', 'images',
              'metadata', 'headings', 'encoding', 'accessibility', 'security', 'performance')
DEFAULTS = dict(config_version=2, language='de', max_pages=100, max_depth=3,
                max_resources=300, timeout=10, max_bytes=5_000_000, delay=0.1,
                external_links=True, robots=True, categories=list(CATEGORIES),
                source_url='https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/sprachpakete',
                update_url='https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/version.json', update_check=False,
                update_interval_value=1, update_interval_unit='weeks', last_update_check='')

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def config_dir():
    return ROOT / '.config' if os.environ.get('CHECKWEB_DEV') == '1' else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'checkweb'

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def settings():
    result = DEFAULTS.copy()
    result['categories'] = list(CATEGORIES)
    path = config_dir() / 'settings.json'
    try:
        saved = json.loads(path.read_text('utf-8'))
        if not isinstance(saved, dict): raise ValueError('settings must be an object')
        for key, default in DEFAULTS.items():
            value = saved.get(key, default)
            if type(value) is type(default): result[key] = value
        if type(saved.get('config_version', 1)) is int and saved.get('config_version', 1) < 2:
            for key in ('source_url', 'update_url'):
                if not result[key].strip(): result[key] = DEFAULTS[key]
        result['config_version'] = DEFAULTS['config_version']
    except (OSError, ValueError):
        pass  # Original remains untouched until explicit Save.
    for key, lo, hi in [('max_pages',0,10000),('max_depth',0,20),('max_resources',0,50000),('timeout',0,60),('max_bytes',1024,50_000_000),('update_interval_value',1,365)]:
        result[key] = max(lo,min(hi,result[key]))
    result['delay'] = max(0.05,min(5.0,result['delay']))
    result['categories'] = [c for c in result['categories'] if c in CATEGORIES]
    return result

def tools_available():
    entries = [
        ('html', 'html5lib', 'python3-html5lib', 'module'),
        ('css', 'tinycss2', 'python3-tinycss2', 'module'),
        ('javascript', 'node', 'nodejs', 'command'),
        ('php', 'php', 'php-cli', 'command'),
        ('structured', 'lxml', 'python3-lxml', 'module'),
        ('images', 'PIL', 'python3-pil', 'module'),
        ('html-extra', 'tidy', 'tidy', 'command'),
    ]
    result=[]
    for c,n,p,kind in entries:
        available=bool(importlib.util.find_spec(n)) if kind=='module' else bool(shutil.which(n))
        version=''
        if available:
            try:
                if kind=='module': version=importlib.metadata.version('Pillow' if n=='PIL' else n)
                else:
                    cmd=[n,'--version'] if n!='php' else ['php','-n','--version']
                    env=os.environ.copy()
                    for key in ('NODE_OPTIONS','NODE_PATH','PHPRC','PHP_INI_SCAN_DIR'):env.pop(key,None)
                    version=subprocess.run(cmd,capture_output=True,text=True,timeout=2,env=env).stdout.splitlines()[0][:150]
            except (OSError,ValueError,IndexError,subprocess.TimeoutExpired,importlib.metadata.PackageNotFoundError):pass
        result.append(dict(category=c,name=n,package=p,available=available,kind=kind,version=version))
    return result


@dataclass
class Finding:
    severity: str
    category: str
    target: str
    code: str
    detail: str = ''
    line: int = 0
    column: int = 0
    tool: str = 'checkweb'
    destination: str = ''
    http_status: int = 0
    scope: str = ''
    link_text: str = ''
    resource_type: str = ''

@dataclass
class Report:
    mode: str
    target: str
    selected: list
    started: str = field(default_factory=now)
    finished: str = ''
    status: str = 'running'
    version: str = VERSION
    schema_version: int = 1
    findings: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    resources: int = 0
    options: dict = field(default_factory=dict)
    tools: list = field(default_factory=list)
    limits: dict = field(default_factory=dict)
    resource_counts: dict = field(default_factory=dict)
    resource_details: list = field(default_factory=list)
    duration_seconds: float = 0.0
    incomplete_reasons: list = field(default_factory=list)

    def data(self): return asdict(self)
