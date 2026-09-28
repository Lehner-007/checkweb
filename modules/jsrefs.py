"""Conservative literal fetch()/XHR GET discovery; never execute JavaScript.

Only fetch('literal') without options and .open('GET'|'HEAD', 'literal')
are supported. Computed URLs, templates and calls with options are skipped.
"""
import ast
import re

TOKENS=re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|[^\s]''')

def literal(token):
    if not token or token[0] not in ('"',"'"):return None
    try:
        value=ast.literal_eval(token)
        return value if isinstance(value,str) and '\\' not in value else None
    except (ValueError,SyntaxError):return None

def requests_in(text):
    tokens=[m for m in TOKENS.finditer(text) if not m.group().startswith(('//','/*'))]
    for i,match in enumerate(tokens):
        t=[x.group() for x in tokens[i:i+8]]
        url=None
        if len(t)>=4 and t[:2]==['fetch','('] and t[3]==')':
            if i and tokens[i-1].group()=='.':continue
            url=literal(t[2])
        elif len(t)>=7 and t[:3]==['.','open','('] and t[4]==',' and t[6] in (',',')'):
            if literal(t[3]) in ('GET','HEAD'):url=literal(t[5])
        if url:yield url,text.count('\n',0,match.start())+1
