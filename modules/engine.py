"""Read-only website checks. No target code is executed or forms submitted."""
from collections import deque, Counter
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,urljoin,urldefrag,unquote,parse_qsl,urlencode
from urllib.robotparser import RobotFileParser
from datetime import datetime
import codecs
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import requests
from urllib3.exceptions import ReadTimeoutError
from bs4 import BeautifulSoup, UnicodeDammit
from .model import VERSION,Report, Finding, CATEGORIES, tools_available, now

TEXT_EXT = {'.html','.htm','.css','.js','.mjs','.cjs','.php','.json','.xml','.svg','.txt'}
FONT_EXT = {'.woff','.woff2','.ttf','.otf','.eot'}
IMAGE_EXT = {'.png','.jpg','.jpeg','.gif','.webp','.bmp','.ico','.tiff'}
SKIP_DIRS = {'.git','.venv','venv','node_modules','__pycache__','.config'}
TOKEN = re.compile(r'(pass|secret|token|api.?key|authorization|cookie)',re.I)

class Cancelled(Exception): pass
class Skipped(Exception): pass


def display_url(url):
    try:
        p = urlsplit(str(url))
        if p.scheme not in ('http','https'): return str(url)
        host = p.hostname or ''
        if ':' in host: host = '['+host+']'
        if p.port: host += ':'+str(p.port)
        return urlunsplit((p.scheme,host,p.path,urlencode([(k,'[redacted]' if TOKEN.search(k) else v) for k,v in parse_qsl(p.query,keep_blank_values=True)]),p.fragment))
    except ValueError: return '[invalid URL]'


def normalize_url_input(url):
    url=str(url).strip()
    if url.startswith('//'):return 'https:'+url
    if '://' not in url and not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:(?![0-9])',url):
        return 'https://'+url
    return url


def canonical(url):
    p = urlsplit(url)
    if p.scheme.lower() not in ('http','https') or not p.hostname or p.username or p.password:
        raise ValueError('HTTP/HTTPS URL without embedded credentials required')
    host = p.hostname.encode('idna').decode().lower()
    if ':' in host: host = '['+host+']'
    port = p.port
    if port and not (p.scheme.lower()=='http' and port==80 or p.scheme.lower()=='https' and port==443): host += ':'+str(port)
    return urlunsplit((p.scheme.lower(),host,p.path or '/',p.query,''))


def origin(url):
    p = urlsplit(url)
    return p.scheme,p.netloc

class Scanner:
    def __init__(self, mode, target, options, callback=None, cancel=None):
        if mode=='online':target=normalize_url_input(target)
        self.mode,self.target,self.options = mode,str(target),options.copy()
        self.selected = set(options.get('categories',CATEGORIES)) & set(CATEGORIES)
        self.report = Report(mode,display_url(target),sorted(self.selected),options={k:v for k,v in options.items() if k not in ('source_url','update_url')},tools=tools_available())
        self.callback = callback or (lambda *a:None)
        self.cancel = cancel or threading.Event()
        self.session = requests.Session()
        self.session.headers['User-Agent'] = f'checkweb/{VERSION} (+read-only website diagnostics)'
        self.session.trust_env = False
        self.cache = {}
        self.robots = {}
        self.robots_unavailable = set()
        self.ids = {}
        self.refs = []
        self.ref_texts = {}
        self.reference_context = {}
        self.seen_findings = set()
        self.seen_checks = set()
        self.root = None
        self.network_count = 0
        self.blocked_origins = set()
        self.analyzed_resources = set()
        self.inventory = {}
        self.terminal_resources = set()
        self.redirect_aliases = {}

    def resource_key(self,target):
        target=str(target)
        if target.startswith(('http://','https://')):return canonical(target)
        return str(Path(target).expanduser().resolve())

    def discover(self,target,requirement='link'):
        key=self.resource_key(target)
        item=self.inventory.setdefault(key,{'required':set(),'done':set(),'type':self.resource_type(key),'http_status':0,'references':[]})
        item['required'].add(requirement)
        if key in self.terminal_resources:item['done'].update(item['required'])
        return key

    @staticmethod
    def resource_type(target,kind='',ext=None):
        ext=ext or Path(urlsplit(str(target)).path).suffix.lower()
        if kind=='fetch':return 'fetch'
        if ext in FONT_EXT:return 'font'
        if ext in IMAGE_EXT | {'.svg'} or kind=='img':return 'image'
        if ext=='.css':return 'css'
        if ext in {'.js','.mjs','.cjs'} or kind=='script':return 'javascript'
        if ext in {'.html','.htm','.php'} or kind in ('a','iframe'):return 'html'
        return 'other'

    def reference(self,dest,source,kind,line,value):
        key=self.discover(dest)
        item=self.inventory[key]
        type_=self.resource_type(dest,kind)
        if type_!='other':item['type']=type_
        text=self.ref_texts.get((source,value,line),'')
        ref=dict(source=display_url(str(source)),line=line or 0,link_text=text)
        if ref not in item['references']:item['references'].append(ref)
        self.reference_context[(display_url(str(source)),display_url(key),line or 0)]=(text,type_)
        return key

    def assessed(self,target,requirement='link',terminal=False):
        key=self.discover(target,requirement)
        self.inventory[key]['done'].add(requirement)
        if terminal:
            self.terminal_resources.add(key)
            self.inventory[key]['done'].update(self.inventory[key]['required'])

    def content_assessed(self,target,actual=None):
        actual=actual or target
        bad=any(c['target']==display_url(str(actual)) and c['status'] in ('unavailable','tool_failed') for c in self.report.checks)
        if not bad:
            self.assessed(target,'content')
            final_key=self.resource_key(actual)
            for alias,final in self.redirect_aliases.items():
                if final==final_key and 'content' in self.inventory[alias]['required']:self.assessed(alias,'content')

    def target_scope(self,target):
        try:
            host=urlsplit(str(target)).hostname
            if host:
                return 'internal' if self.mode=='online' and host==urlsplit(self.target).hostname else 'external'
            return 'internal' if self.root and Path(target).resolve().is_relative_to(self.root) else 'unknown'
        except ValueError:return 'unknown'

    def stopcheck(self):
        if self.cancel.is_set(): raise Cancelled()

    def add(self, severity, category, target, code, detail='', line=0, column=0, tool='checkweb',destination='',http_status=0):
        if code=='limit':
            self.report.limits[detail]=self.options.get(detail)
            target=self.target
        target=display_url(str(target))
        # Tool output is diagnostic data, not instructions; do not expose full source lines.
        detail = str(detail)[:1000]
        destination=display_url(str(destination or target))
        key=(severity,category,target,code,detail,line,destination,http_status)
        if key not in self.seen_findings:
            self.seen_findings.add(key)
            text,type_=self.reference_context.get((target,destination,line or 0),('',self.resource_type(destination)))
            self.report.findings.append(Finding(severity,category,target,code,detail,line or 0,column or 0,tool,destination,http_status,self.target_scope(destination),text,type_))

    def record(self, target, category, status='done', tool='checkweb'):
        key=(display_url(str(target)),category,status,tool)
        if key not in self.seen_checks:
            self.seen_checks.add(key)
            self.report.checks.append(dict(target=key[0],category=category,status=status,tool=tool))

    def http_result(self,status,url,source=None,line=0,category='links'):
        if 200<=status<300:return
        if status in (404,410):severity,code='error','http_missing'
        elif status==401:severity,code='info','http_auth'
        elif status==403:severity,code='info','http_forbidden'
        elif status==429:severity,code='info','rate_limit'
        elif 500<=status<600:severity,code='warning','http_server'
        elif 300<=status<400:severity,code='info','redirect_pending'
        else:severity,code='warning','http_status'
        self.add(severity,category,source or url,code,f'{display_url(url)}: HTTP {status}',line,destination=url,http_status=status)

    def run(self):
        started=time.monotonic()
        try:
            if not self.selected: raise ValueError('No checks selected')
            if self.mode=='local': self.local()
            elif self.mode=='online': self.online()
            else: raise ValueError('Invalid mode')
            self.stopcheck()
            self.report.status='incomplete' if self.report.limits else 'complete'
        except Cancelled:
            self.report.status='cancelled'
        except Exception as exc:
            self.report.status='failed'
            self.add('error','system',self.target,'scan_failed',type(exc).__name__+': '+str(exc))
        finally:
            for category in sorted(self.selected):
                if not any(x['category']==category for x in self.report.checks): self.record(self.target,category,'not_applicable')
            self.report.finished=now()
            self.report.duration_seconds=max(0,time.monotonic()-started)
            checked=sum(item['required']<=item['done'] for item in self.inventory.values())
            self.report.resource_counts=dict(found=len(self.inventory),checked=checked,unchecked=len(self.inventory)-checked,
                                             analyzed=len(self.analyzed_resources),http_requests=self.network_count)
            self.report.resources=len(self.analyzed_resources)
            self.report.resource_details=[dict(target=display_url(key),scope=self.target_scope(key),
                required=sorted(item['required']),done=sorted(item['done']),checked=item['required']<=item['done'],
                type=item['type'],http_status=item['http_status'],references=item['references'])
                for key,item in self.inventory.items()]
            if self.report.resource_counts['unchecked']:self.report.incomplete_reasons.append('pending_resources')
            if any(c['status'] in ('unavailable','tool_failed') for c in self.report.checks):self.report.incomplete_reasons.append('missing_checks')
            if self.report.status=='complete' and self.report.incomplete_reasons:self.report.status='incomplete'

            self.session.close()
        return self.report

    def local(self):
        self.root=Path(self.target).expanduser().resolve()
        if not self.root.is_dir(): raise ValueError('Not a directory')
        count=0
        for folder, dirs, files in os.walk(self.root,followlinks=False):
            self.stopcheck()
            if self.options['max_resources'] and count >= self.options['max_resources']:
                self.add('info','system',self.root,'limit','max_resources'); break
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(folder)/d).is_symlink())
            for name in sorted(files):
                self.stopcheck()
                path=Path(folder)/name
                if path.is_symlink(): continue
                if path.suffix.lower() not in TEXT_EXT | IMAGE_EXT | FONT_EXT: continue
                self.discover(path,'content')
                if self.options['max_resources'] and count>=self.options['max_resources']:
                    self.add('info','system',self.root,'limit','max_resources'); break
                count+=1
                self.callback(count,str(path))
                try:
                    if path.stat().st_size>self.options['max_bytes']:
                        self.add('info','system',path,'too_large'); continue
                    data=path.read_bytes()
                    self.report.resources+=1
                    self.analyze(data,str(path),path.suffix.lower())
                    self.content_assessed(path)
                except (OSError,ValueError) as exc:
                    self.add('warning','system',path,'read_failed',type(exc).__name__)
        if 'links' in self.selected or 'images' in self.selected:
            self.local_links()

    def command(self, args, data):
        self.stopcheck()
        env=os.environ.copy()
        for k in ('NODE_OPTIONS','NODE_PATH','PHPRC','PHP_INI_SCAN_DIR'): env.pop(k,None)
        with tempfile.TemporaryDirectory(prefix='checkweb-') as cwd, tempfile.TemporaryFile() as inp, tempfile.TemporaryFile() as out:
            inp.write(data); inp.seek(0)
            process=subprocess.Popen(args,stdin=inp,stdout=out,stderr=subprocess.STDOUT,cwd=cwd,env=env,start_new_session=True)
            started=time.monotonic()
            try:
                while process.poll() is None:
                    self.stopcheck()
                    if self.options['timeout'] and time.monotonic()-started>self.options['timeout']: raise TimeoutError('tool timeout')
                    if out.tell()>1_000_000: raise ValueError('tool output limit')
                    self.cancel.wait(.03)
                out.seek(0)
                return process.returncode,out.read(65536).decode('utf-8','replace')
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGKILL)
                    process.wait()

    def analyze(self,data,target,ext,headers=None,elapsed=0):
        self.stopcheck()
        headers=headers or {}
        if target in self.analyzed_resources: return
        self.analyzed_resources.add(target)
        key=self.discover(target,'content')
        type_=self.resource_type(target,ext=ext)
        if type_!='other':self.inventory[key]['type']=type_
        if 'performance' in self.selected:
            self.record(target,'performance')
            if len(data)>1_000_000: self.add('warning','performance',target,'large_resource',str(len(data)))
            if elapsed>2: self.add('warning','performance',target,'slow_response',f'{elapsed:.2f} s')
            if self.mode=='online' and ext in {'.css','.js','.html','.htm'} and len(data)>1024 and not headers.get('Content-Encoding'):
                self.add('info','performance',target,'compression')
            if self.mode=='online' and ext in {'.css','.js'} and not headers.get('Cache-Control'):
                self.add('info','performance',target,'cache_header')
        if ext in IMAGE_EXT:
            if 'images' in self.selected:
                try:
                    from PIL import Image
                    with Image.open(io.BytesIO(data)) as im: im.verify()
                    self.record(target,'images',tool='Pillow')
                except ImportError: self.unavailable(target,'images','python3-pil')
                except Exception: self.add('error','images',target,'image_invalid');self.record(target,'images',tool='Pillow')
            return
        if ext not in TEXT_EXT: return
        text=self.decode(data,target,headers)
        if ext in {'.html','.htm'}:
            self.html(text,target,headers)
        if ext=='.php' and 'php' in self.selected:
            self.syntax(target,'php',['php','-n','-l'],data)
        if ext in {'.js','.mjs','.cjs'} and 'javascript' in self.selected:
            module=ext=='.mjs' or (ext!='.cjs' and bool(re.search(r'^\s*(import\s|export\s)',text,re.M)))
            self.syntax(target,'javascript',['node','--input-type='+('module' if module else 'commonjs'),'--check'],data)
        if ext=='.css' and {'css','links','images'} & self.selected: self.css(text,target)
        if ext in {'.json','.xml','.svg'} and 'structured' in self.selected:
            try:
                if ext=='.json': json.loads(text)
                else:
                    from lxml import etree
                    etree.fromstring(data,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False))
                self.record(target,'structured')
            except ImportError: self.unavailable(target,'structured','python3-lxml')
            except Exception as exc:
                pos=getattr(exc,'position',(getattr(exc,'lineno',0),0))
                self.add('error','structured',target,'syntax',type(exc).__name__,pos[0],pos[1]); self.record(target,'structured')
        if ext=='.php' and 'security' in self.selected:
            self.record(target,'security')
            for i,line in enumerate(text.splitlines(),1):
                if re.search(r'\beval\s*\(',line) and re.search(r'\$_(?:GET|POST|REQUEST)',line):
                    self.add('warning','security',target,'php_eval','',i)

    def unavailable(self,target,category,package):
        self.record(target,category,'unavailable')
        self.add('info',category,target,'tool_missing',package)

    def syntax(self,target,category,args,data):
        if not shutil.which(args[0]): self.unavailable(target,category,'php-cli' if category=='php' else 'nodejs');return
        try:
            rc,out=self.command(args,data)
            self.record(target,category,'done' if rc in (0,1,255) else 'tool_failed',args[0])
            if rc:
                match=re.search(r'(?:on line |\[stdin\]:)(\d+)',out)
                # Only summary lines: JavaScript/PHP excerpts may contain private data.
                summary=next((l for l in out.splitlines() if 'SyntaxError:' in l or 'Parse error:' in l or 'Fatal error:' in l),'Syntax check failed')
                summary=re.sub(r'"[^"]*"', '"…"',summary)
                self.add('error',category,target,'syntax',summary,int(match[1]) if match else 0,tool=args[0])
        except (OSError,TimeoutError,ValueError) as exc:
            self.record(target,category,'tool_failed',args[0]);self.add('warning',category,target,'tool_failed',type(exc).__name__)

    def decode(self,data,target,headers):
        declared=re.search(r'charset\s*=\s*["\']?([^;\s"\'>]+)',headers.get('Content-Type',''),re.I)
        if not declared: declared=re.search(br'charset\s*=\s*["\']?([^;\s"\'>]+)',data[:4096],re.I)
        encoding=(declared[1].decode('ascii','replace') if isinstance(declared[1],bytes) else declared[1]) if declared else 'utf-8-sig'
        try: text=data.decode(encoding)
        except (UnicodeError,LookupError):
            text=UnicodeDammit(data).unicode_markup or data.decode('utf-8','replace')
            if 'encoding' in self.selected: self.add('warning','encoding',target,'encoding_invalid',encoding)
        if 'encoding' in self.selected: self.record(target,'encoding')
        return text

    def html(self,text,target,headers):
        soup=BeautifulSoup(text,'html.parser')
        self.ids[target]={x.get('id') for x in soup.find_all(id=True)} | {x.get('name') for x in soup.find_all('a',attrs={'name':True})}
        if 'html' in self.selected:
            try:
                import html5lib
                parser=html5lib.HTMLParser(strict=False)
                parser.parse(text)
                for (line,col),code,params in parser.errors[:100]:
                    self.add('warning','html',target,'html_parse',code,line,col,tool='html5lib')
                self.record(target,'html',tool='html5lib')
            except ImportError: self.unavailable(target,'html','python3-html5lib')
            counts=Counter(x.get('id') for x in soup.find_all(id=True))
            for id_,n in counts.items():
                if n>1: self.add('error','html',target,'duplicate_id',id_)
        if 'metadata' in self.selected:
            self.record(target,'metadata')
            if not soup.title or not soup.title.get_text(strip=True): self.add('warning','metadata',target,'title_missing')
            desc=soup.find('meta',attrs={'name':re.compile('^description$',re.I)})
            if not desc or not desc.get('content','').strip(): self.add('info','metadata',target,'description_missing')
            if not soup.find('meta',attrs={'name':re.compile('^viewport$',re.I)}):self.add('info','metadata',target,'viewport_missing')
        if 'headings' in self.selected:
            self.record(target,'headings')
            hs=soup.find_all(re.compile('^h[1-6]$'))
            if not soup.find('h1'): self.add('warning','headings',target,'h1_missing')
            previous=0
            for h in hs:
                level=int(h.name[1])
                if previous and level>previous+1: self.add('warning','headings',target,'heading_jump',f'h{previous} → h{level}',h.sourceline)
                previous=level
        if 'accessibility' in self.selected:
            self.record(target,'accessibility')
            if not soup.html or not soup.html.get('lang'): self.add('warning','accessibility',target,'lang_missing')
            for image in soup.find_all('img'):
                if not image.has_attr('alt'): self.add('warning','accessibility',target,'alt_missing','',image.sourceline)
            labels={x.get('for') for x in soup.find_all('label',attrs={'for':True})}
            for control in soup.find_all(['input','select','textarea']):
                if control.get('type','').lower() in ('hidden','submit','button','reset','image'): continue
                if not (control.get('aria-label') or control.get('aria-labelledby') or control.get('id') in labels or control.find_parent('label')):
                    self.add('warning','accessibility',target,'label_missing','',control.sourceline)
            for anchor in soup.find_all(['a','button']):
                if not (anchor.get_text(strip=True) or anchor.get('aria-label') or anchor.get('aria-labelledby') or any(x.get('alt') for x in anchor.find_all('img'))):
                    self.add('warning','accessibility',target,'name_missing','',anchor.sourceline)
        if 'security' in self.selected:
            self.record(target,'security')
            if self.mode=='online':
                if urlsplit(target).scheme=='http':self.add('warning','security',target,'plain_http')
                if not headers.get('Content-Security-Policy'):self.add('info','security',target,'csp_missing')
                if headers.get('X-Content-Type-Options','').lower()!='nosniff':self.add('info','security',target,'nosniff_missing')
            for form in soup.find_all('form'):
                if form.find('input',attrs={'type':'password'}) and form.get('method','get').lower()!='post':
                    self.add('warning','security',target,'password_get','',form.sourceline)
        base=soup.find('base',href=True)
        base_href=base.get('href') if base else ''
        for node in soup.find_all(['a','img','script','link','iframe','source','video','audio']):
            attr='href' if node.name in ('a','link') else 'src'
            value=node.get(attr)
            if value:
                self.refs.append((target,value,node.name,node.sourceline or 0,base_href))
                self.ref_texts[(target,value,node.sourceline or 0)]=node.get_text(' ',strip=True)[:500] if node.name=='a' else ''
                if 'security' in self.selected and target.startswith('https:') and value.startswith('http:') and node.name!='a':
                    self.add('warning','security',target,'mixed_content',display_url(value),node.sourceline)
        if {'css','links','images'} & self.selected:
            for style in soup.find_all('style'): self.css(style.get_text(),target,base_href)
        for script in soup.find_all('script',src=False):
            if script.get('type','').lower() in ('','text/javascript','application/javascript','module'):
                self.javascript_refs(script.get_text(),target,self.document_base(target,base_href) ,max(0,(script.sourceline or 1)-1))
        if 'javascript' in self.selected:
            for script in soup.find_all('script',src=False):
                if script.get('type','').lower() not in ('','text/javascript','application/javascript','module'):continue
                self.syntax(target,'javascript',['node','--input-type='+('module' if script.get('type')=='module' else 'commonjs'),'--check'],script.get_text().encode('utf-8'))

    def document_base(self,target,base):
        if self.mode=='online' or base.startswith(('http:','https:')):return urljoin(target,base)
        if not base:return str(Path(target).parent)+'/'
        resolved=self.root/base.lstrip('/') if base.startswith('/') else Path(target).parent/base
        return str(resolved)+('/' if base.endswith('/') else '')

    def javascript_refs(self,text,source,document_base,line_offset=0):
        if 'links' not in self.selected:return
        from .jsrefs import requests_in
        for value,line in requests_in(text):
            self.refs.append((source,value,'fetch',line+line_offset,document_base))

    def css(self,text,target,base=''):
        try: import tinycss2
        except ImportError: self.unavailable(target,'css','python3-tinycss2');return
        if 'css' in self.selected:self.record(target,'css',tool='tinycss2')
        def walk(nodes):
            for node in nodes:
                if node.type=='error' and 'css' in self.selected: self.add('warning','css',target,'syntax',node.message,node.source_line,node.source_column,tool='tinycss2')
                if node.type=='qualified-rule':
                    walk(tinycss2.parse_declaration_list(node.content,skip_comments=True,skip_whitespace=True))
                elif node.type=='at-rule' and node.content is not None:
                    if node.lower_at_keyword in ('media','supports','layer','container','keyframes'):
                        walk(tinycss2.parse_rule_list(node.content,skip_comments=True,skip_whitespace=True))
                    elif node.lower_at_keyword in ('font-face','page'):
                        walk(tinycss2.parse_declaration_list(node.content,skip_comments=True,skip_whitespace=True))
                for attr in ('value','prelude','arguments'):
                    value=getattr(node,attr,None)
                    if isinstance(value,list): walk(value)
                if node.type=='at-rule' and node.lower_at_keyword=='import':
                    tokens=[x for x in node.prelude if x.type not in ('whitespace','comment')]
                    if tokens and tokens[0].type=='string': self.refs.append((target,tokens[0].value,'resource',node.source_line,base))
                if node.type=='url': self.refs.append((target,node.value,'resource',node.source_line,base))
                if node.type=='function' and node.lower_name=='url':
                    value=tinycss2.serialize(node.arguments).strip().strip('"\'')
                    self.refs.append((target,value,'resource',node.source_line,base))
        walk(tinycss2.parse_stylesheet(text,skip_comments=True,skip_whitespace=True))

    def local_links(self):
        for source,value,kind,line,base in self.refs:
            self.stopcheck()
            cat='images' if kind=='img' else 'links'
            if cat not in self.selected:continue
            parsed=urlsplit(value)
            if parsed.scheme in ('data','mailto','tel','javascript'):continue
            if parsed.scheme in ('http','https') or value.startswith('//') or base.startswith(('http:','https:')):
                self.reference(urljoin(base or 'https://localhost/',value),source,kind,line,value)
                if not self.options.get('external_links',True):
                    self.record(value,cat,'not_checked');continue
                try:
                    url=urljoin(base or 'https://localhost/',value)
                    result=self.fetch(url,body=False,source=source,line=line)
                    if result:self.http_result(result[2],url,source,line,cat)
                except Skipped: pass
                continue
            if parsed.scheme:continue
            self.record(source,cat)
            raw=unquote(parsed.path)
            base_dir=Path(source).parent
            if kind=='fetch' and base and not base.startswith(('http:','https:')):
                base_dir=Path(base).parent if not base.endswith('/') else Path(base)
            elif base:
                basepath=unquote(urlsplit(base).path)
                base_dir=self.root/basepath.lstrip('/') if basepath.startswith('/') else base_dir/basepath
                if not basepath.endswith('/'):base_dir=base_dir.parent
            dest=((self.root/raw.lstrip('/')) if raw.startswith('/') else (base_dir/raw)) if raw else Path(source)
            dest=dest.resolve()
            if dest.is_dir():
                dest=next((dest/n for n in ('index.html','index.htm','index.php') if (dest/n).is_file()),dest)
            self.reference(dest,source,kind,line,value)
            if not dest.is_relative_to(self.root): self.add('info',cat,source,'outside_root',value,line);continue
            if dest.is_dir():
                dest=next((dest/n for n in ('index.html','index.htm','index.php') if (dest/n).is_file()),dest)
            if dest.exists() or dest.suffix:self.assessed(dest)
            if not dest.exists():
                code='route_unknown' if not dest.suffix else 'file_missing'
                self.add('error' if dest.suffix else 'info',cat,source,code,value,line,destination=str(dest))
            elif kind=='script' and dest.is_file():
                try:
                    if dest.stat().st_size<=self.options['max_bytes']:
                        self.javascript_refs(dest.read_text('utf-8'),str(dest),str(base_dir)+'/')
                except (OSError,UnicodeError):pass
            elif parsed.fragment and dest.suffix in ('.html','.htm'):
                if str(dest) not in self.ids:
                    try:
                        if dest.stat().st_size>self.options['max_bytes']:continue
                        soup=BeautifulSoup(dest.read_bytes(),'html.parser')
                        self.ids[str(dest)]={x.get('id') for x in soup.find_all(id=True)} | {x.get('name') for x in soup.find_all('a',attrs={'name':True})}
                    except OSError:continue
                if unquote(parsed.fragment) not in self.ids.get(str(dest),set()):self.add('warning',cat,source,'fragment_missing',value,line)

    def allowed(self,url):
        if not self.options.get('robots',True):return True
        key=origin(url)
        if key not in self.robots:
            rp=RobotFileParser()
            data=self.fetch(urlunsplit((*key,'/robots.txt','','')),robot=True)
            if not data:
                self.robots_unavailable.add(key)
                rp.disallow_all=True
                self.robots[key]=rp
                return False
            if data[2] in (401,403): rp.disallow_all=True
            elif data[2]>=500 or 300<=data[2]<400:
                self.robots_unavailable.add(key)
                rp.disallow_all=True
            elif data[2]>=400:rp.allow_all=True
            else:rp.parse(data[0].decode('utf-8','replace').splitlines())
            self.robots[key]=rp
        return self.robots[key].can_fetch('checkweb',url)

    def fetch(self,url,body=True,robot=False,source=None,line=0):
        url=canonical(url)
        if not robot:self.discover(url,'content' if body else 'link')
        if origin(url) in self.blocked_origins:
            self.record(url,'links','not_checked','requests');raise Skipped()
        key=(url,body,robot)
        if key in self.cache:return self.cache[key]
        self.stopcheck()
        if self.options['max_resources'] and self.network_count>=self.options['max_resources']:
            self.add('info','system',url,'limit','max_resources');raise Skipped()
        if not robot and not self.allowed(url):
            self.record(url,'links','not_checked','requests')
            self.add('info','links',source or url,'robots_unavailable' if origin(url) in self.robots_unavailable else 'robots_denied',line=line,destination=url);raise Skipped()
        current=url
        visited=set()
        try:
            for step in range(6):
                self.stopcheck()
                if current in visited:raise ValueError('redirect loop')
                visited.add(current)
                if self.options['max_resources'] and self.network_count>=self.options['max_resources']:
                    self.add('info','system',url,'limit','max_resources');raise Skipped()
                self.network_count+=1
                if self.cancel.wait(self.options.get('delay',.1)):raise Cancelled()
                started=time.monotonic()
                # Stream GET, even for link probes; only bounded content is read when requested.
                with self.session.get(current,timeout=(min(5,self.options['timeout']),self.options['timeout']) if self.options['timeout'] else None,stream=True,allow_redirects=False) as response:
                    code=response.status_code
                    if not robot:
                        for alias in visited:
                            self.inventory[self.discover(alias)]['http_status']=code
                    if code in (301,302,303,307,308) and response.headers.get('Location'):
                        nxt=canonical(urljoin(current,response.headers['Location']))
                        if not robot:self.discover(nxt,'content' if body else 'link')
                        self.add('info','links',source or url,'redirect',display_url(nxt),line,destination=nxt,http_status=code)
                        if step==5:raise ValueError('redirect limit')
                        if origin(nxt)!=origin(current):
                            self.record(url,'links','not_checked','requests')
                            self.add('info','links',source or url,'redirect_boundary',display_url(nxt),line,destination=nxt,http_status=code);raise Skipped()
                        current=nxt;continue
                    if code==429:
                        self.blocked_origins.add(origin(url))
                        self.record(url,'links','not_checked','requests')
                        self.add('info','links',source or url,'rate_limit','HTTP 429; Retry-After: '+response.headers.get('Retry-After','—'),line,destination=url,http_status=429)
                        raise Skipped()
                    if not robot:
                        self.record(url,'links','done' if 200<=code<300 or code in (404,410) else 'not_checked','requests')
                    if not robot and (200<=code<300 or code in (404,410)):
                        for alias in visited:
                            self.assessed(alias,terminal=code in (404,410))
                            self.redirect_aliases[alias]=current
                    content=bytearray()
                    if body and code<300:
                        for chunk in response.iter_content(65536):
                            self.stopcheck()
                            if self.options['timeout'] and time.monotonic()-started>self.options['timeout']:raise TimeoutError('body timeout')
                            if len(content)+len(chunk)>self.options['max_bytes']:
                                self.record(url,'system','not_checked','requests')
                                self.add('info','system',url,'too_large');raise Skipped()
                            content.extend(chunk)
                    result=(bytes(content),dict(response.headers),code,current,time.monotonic()-started)
                    self.cache[key]=result
                    return result
        except (requests.RequestException,TimeoutError,ValueError) as exc:
            self.record(url,'links','not_checked','requests')
            code='http_timeout' if any(isinstance(item,(requests.Timeout,TimeoutError,ReadTimeoutError)) for item in (exc,exc.__context__,exc.__cause__,*exc.args)) else 'network_error'
            self.add('warning','links',source or url,code,type(exc).__name__,line,destination=url)
            self.cache[key]=None
        return None

    def online(self):
        start=canonical(self.target)
        self.discover(start,'content')
        queue=deque([(start,0)])
        visited=set()
        depth_skipped=set()
        if 'php' in self.selected:self.record(start,'php','not_applicable')
        while queue:
            self.stopcheck()
            url,depth=queue.popleft()
            if url in visited or url in self.terminal_resources:continue
            if self.options['max_pages'] and len(visited)>=self.options['max_pages']:
                self.add('info','system',start,'limit','max_pages');break
            visited.add(url)
            self.callback(len(visited),display_url(url))
            try: result=self.fetch(url)
            except Skipped:continue
            if not result:continue
            data,headers,status,final,elapsed=result
            if status>=300:
                if not any(f.destination==display_url(url) and f.http_status==status for f in self.report.findings):
                    self.http_result(status,url)
                continue
            self.report.resources+=1
            ext=self.extension(final,headers)
            begin=len(self.refs)
            self.analyze(data,final,ext,headers,elapsed)
            self.content_assessed(url,final)
            self.content_assessed(final)
            ref_index=begin
            while ref_index<len(self.refs):
                source,value,kind,line,base=self.refs[ref_index]
                ref_index+=1
                try: resolved=urljoin(urljoin(source,base),value); dest=canonical(resolved)
                except ValueError:continue
                internal=origin(dest)==origin(start)
                cat='images' if kind=='img' else 'links'
                self.reference(dest,source,kind,line,value)
                if internal and kind=='a' and (not self.options['max_depth'] or depth<self.options['max_depth']):self.discover(dest,'content')
                if kind=='a':
                    if 'links' in self.selected:
                        if internal or self.options.get('external_links',True):
                            try:
                                probe=self.fetch(dest,body=False,source=source,line=line)
                                if probe:self.http_result(probe[2],dest,source,line)
                            except Skipped:pass
                        else:self.record(dest,'links','not_checked')
                    if internal and dest not in visited:
                        if (not self.options['max_depth'] or depth<self.options['max_depth']):queue.append((dest,depth+1))
                        else:depth_skipped.add(dest)
                else:
                    # Referenced resources are read once within the global request budget.
                    need=cat in self.selected or (kind in ('script','link','resource') and bool({'css','javascript','performance'} & self.selected))
                    if not need:continue
                    try: res=self.fetch(dest,source=source,line=line)
                    except Skipped:continue
                    if not res:continue
                    if res[2]>=300:self.http_result(res[2],dest,source,line,cat);continue
                    if cat in self.selected:self.record(source,cat)
                    self.report.resources+=1
                    self.analyze(res[0],res[3],self.extension(res[3],res[1]),res[1],res[4])
                    self.content_assessed(dest,res[3])
                    self.content_assessed(res[3])
                    if kind=='script':
                        self.javascript_refs(self.decode(res[0],res[3],res[1]),res[3],urljoin(source,base))
        if depth_skipped-visited-self.terminal_resources:
            self.add('info','system',start,'limit','max_depth')
        # Anchors only when target HTML was fetched; no fabricated failure for unvisited pages.
        if 'links' in self.selected:
            for source,value,kind,line,base in self.refs:
                if kind!='a':continue
                resolved=urljoin(urljoin(source,base),value)
                dest,frag=urldefrag(resolved)
                try:dest=canonical(dest)
                except ValueError:continue
                if frag and dest in self.ids and unquote(frag) not in self.ids[dest]:self.add('warning','links',source,'fragment_missing',value,line)

    @staticmethod
    def extension(url,headers):
        mime=headers.get('Content-Type','').split(';')[0].lower()
        mapping={'text/html':'.html','application/xhtml+xml':'.html','text/css':'.css','application/javascript':'.js','text/javascript':'.js','application/json':'.json','image/svg+xml':'.svg','application/xml':'.xml','text/xml':'.xml','image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp','image/gif':'.gif'}
        return mapping.get(mime,Path(urlsplit(url).path).suffix.lower())
