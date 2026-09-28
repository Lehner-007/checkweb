"""Grouped, escaped HTML reports and lossless JSON exports."""
from collections import Counter
from html import escape
from pathlib import Path
from datetime import datetime
import json
import base64
import logging
from .lifecycle import log_text
import os
import tempfile
from .i18n import Strings

SECTIONS=('errors','external_errors','manual','indeterminate','warnings','hints','unchecked','redirects')
MANUAL_CODES={'http_auth','http_forbidden'}
INDETERMINATE_CODES={'http_server','http_timeout','http_status','network_error','rate_limit','robots_denied','robots_unavailable','route_unknown','tool_failed'}
UNCHECKED_CODES={'limit','too_large','tool_missing'}
REDIRECT_CODES={'redirect','redirect_boundary','redirect_pending'}


def finding_section(finding):
    if finding.code in INDETERMINATE_CODES:return 'indeterminate'
    if finding.severity=='error' and getattr(finding,'scope','')=='external':return 'external_errors'
    if finding.code in MANUAL_CODES:return 'manual'
    if finding.code in UNCHECKED_CODES:return 'unchecked'
    if finding.code in REDIRECT_CODES:return 'redirects'
    return {'error':'errors','warning':'warnings'}.get(finding.severity,'hints')


def group_findings(findings):
    """Group similar messages while retaining every source, detail and line."""
    groups={}
    for f in findings:
        key=(finding_section(f),f.severity,f.category,f.code,f.tool,getattr(f,'scope',''))
        groups.setdefault(key,[]).append(f)
    return sorted(groups.values(),key=lambda group:(SECTIONS.index(finding_section(group[0])),group[0].category,group[0].code))


def limit_messages(report,tr):
    limits=dict(getattr(report,'limits',{}))
    # Also render reports created before the explicit limits field was introduced.
    for f in report.findings:
        if f.code=='limit':limits.setdefault(f.detail,report.options.get(f.detail,'—'))
    return [tr('limit_'+key,value=value) if key in ('max_resources','max_pages','max_depth') else str(key)+': '+str(value)
            for key,value in limits.items()]


def format_timestamp(value):
    try:return datetime.fromisoformat(value).astimezone().strftime('%d.%m.%Y %H:%M:%S %z')
    except (ValueError,TypeError):return '—'


def format_duration(report):
    seconds=getattr(report,'duration_seconds',0)
    if not seconds:
        try:seconds=(datetime.fromisoformat(report.finished)-datetime.fromisoformat(report.started)).total_seconds()
        except (ValueError,TypeError):return '—'
    seconds=max(0,int(seconds))
    hours,seconds=divmod(seconds,3600)
    minutes,seconds=divmod(seconds,60)
    return (f'{hours} h ' if hours else '')+f'{minutes} min {seconds} s'


def incomplete_messages(report,tr):
    return limit_messages(report,tr)+[tr('reason_'+reason) for reason in getattr(report,'incomplete_reasons',[])]


def watermark_style():
    image=Path(__file__).resolve().parent.parent/'assets'/'report_watermark.png'
    try:
        encoded=base64.b64encode(image.read_bytes()).decode('ascii')
    except OSError:
        logging.warning(log_text('log_watermark',image=image))
        return ''
    return ('<style>body{position:relative;isolation:isolate}'
            'body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;'
            'background-image:url("data:image/png;base64,'+encoded+'");'
            'background-repeat:no-repeat;background-position:center;'
            'background-size:min(72vw,620px) auto;opacity:0.05}'
            '@media (forced-colors:active){body::before{display:none}}</style>')


def html_report(report,language):
    tr=Strings(language)
    e=lambda value:escape(str(value),quote=True)
    counts=Counter(finding_section(f) for f in report.findings)
    unchecked={c['target'] for c in report.checks if c['status']!='done'}
    unchecked.update(f.target for f in report.findings if finding_section(f)=='unchecked')

    direction='rtl' if language.split('-')[0].split('_')[0] in ('ar','he','fa','ur') else 'ltr'
    chunks=['<!doctype html><html lang="'+e(language)+'" dir="'+direction+'"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width"><title>checkweb</title>',
            '<style>body{font:16px sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#202020;background:#fff;line-height:1.5}h1,h2,h3,summary{font-weight:normal}table{border-collapse:collapse;width:100%;margin:1em 0}td,th{border:1px solid #aaa;padding:.5em;text-align:start;vertical-align:top;overflow-wrap:anywhere}th{font-weight:normal;background:#eee}details{margin:1em 0;padding:.5em;border:1px solid #aaa}summary{cursor:pointer}.incomplete{border:2px solid #9c5800;padding:1em}pre{white-space:pre-wrap;overflow-wrap:anywhere}.table{overflow-x:auto}</style></head><body>',
            '<h1>checkweb</h1><p>'+e(report.target)+'</p><h2>'+e(tr('report_summary'))+'</h2>',
            '<p>'+e(tr(report.mode)+' · '+tr(report.status))+'</p>']
    metadata=[('report_target',report.target),('report_mode',tr(report.mode)),('report_status',tr(report.status)),
              ('report_started',format_timestamp(report.started)),('report_finished',format_timestamp(report.finished)),('report_duration',format_duration(report))]
    chunks.append('<dl>'+''.join('<dt>'+e(tr(key))+'</dt><dd>'+e(value)+'</dd>' for key,value in metadata)+'</dl>')
    limits=incomplete_messages(report,tr)
    if limits:
        chunks.append('<div class="incomplete"><p>'+e(tr('incomplete').upper())+'</p>'+''.join('<p>'+e(message)+'</p>' for message in limits)+'</div>')
    resources=getattr(report,'resource_counts',{})
    if resources:
        chunks.append('<dl>'+''.join('<dt>'+e(tr('count_'+key))+'</dt><dd>'+e(resources.get(key,'—'))+'</dd>'
                                    for key in ('found','checked','unchecked','analyzed','http_requests'))+
                      '<dt>'+e(tr('resource_budget'))+'</dt><dd>'+e(tr('unlimited') if report.options.get('max_resources')==0 else report.options.get('max_resources','—'))+'</dd></dl>')
        chunks.append('<p>'+e(tr('count_definition'))+'</p>')
    else:chunks.append('<p>'+e(tr('legacy_counts'))+'</p>')
    chunks.append('<p>'+e(tr('finding_counts'))+'</p><ul>')
    for section in SECTIONS:chunks.append('<li>'+e(tr('section_'+section))+': '+str(counts[section])+'</li>')
    chunks.append('</ul><p>'+e(tr('limits_note'))+'</p>')
    groups=group_findings(report.findings)
    for section in SECTIONS:
        chunks.append('<section><h2>'+e(tr('section_'+section))+'</h2>')
        selected=[g for g in groups if finding_section(g[0])==section and g[0].code!='limit']
        if not selected and not (section=='unchecked' and unchecked):chunks.append('<p>'+e(tr('no_section_findings'))+'</p>')
        for group in selected:
            f=group[0]
            chunks.append('<h3>'+e(tr('msg_'+f.code))+'</h3><p>'+e(tr('fix_'+f.code))+'</p>')
            scope=tr('scope_'+(getattr(f,'scope','') or 'unknown'))
            chunks.append('<p>'+e(tr('cat_'+f.category))+' · '+e(scope)+'</p>')
            if getattr(f,'scope','')=='external':chunks.append('<p>'+e(tr('external_note'))+'</p>')
            prominent=group if section in ('errors','external_errors') else group[:1]
            for item in prominent:
                chunks.append('<dl><dt>'+e(tr('source_location'))+'</dt><dd>'+e(item.target)+'</dd>'+
                    '<dt>'+e(tr('line'))+'</dt><dd>'+e(item.line or '—')+'</dd>'+
                    '<dt>'+e(tr('report_target'))+'</dt><dd>'+e(getattr(item,'destination','') or item.target)+'</dd>'+
                    '<dt>'+e(tr('link_text'))+'</dt><dd>'+e(getattr(item,'link_text','') or '—')+'</dd>'+
                    '<dt>HTTP</dt><dd>'+e(getattr(item,'http_status',0) or '—')+'</dd></dl><p>'+e(item.detail)+'</p>')
            chunks.append('<details><summary>'+e(tr('occurrences',count=len(group)))+' · '+e(tr('cat_'+f.category))+'</summary><div class="table"><table><thead><tr>')
            for key in ('source_location','report_target','target_scope','line','link_text','detail'):chunks.append('<th>'+e(tr(key))+'</th>')
            chunks.append('</tr></thead><tbody>')
            for item in group:
                chunks.append('<tr>'+''.join('<td>'+e(value)+'</td>' for value in (item.target,getattr(item,'destination','') or item.target,tr('scope_'+(getattr(item,'scope','') or 'unknown')),item.line or '—',getattr(item,'link_text','') or '—',item.detail))+'</tr>')
            chunks.append('</tbody></table></div></details>')
        if section=='unchecked':
            pending=[r for r in getattr(report,'resource_details',[]) if not r['checked']]
            if pending:
                chunks.append('<details><summary>'+e(tr('pending_targets',count=len(pending)))+'</summary><ul>')
                chunks.extend('<li>'+e(r['target'])+' · '+e(tr('scope_'+r['scope']))+'</li>' for r in pending)
                chunks.append('</ul></details>')
            checks=[c for c in report.checks if c['status']!='done']
            grouped={}
            for c in checks:grouped.setdefault((c['status'],c['category'],c['tool']),set()).add(c['target'])
            for (status,category,tool),targets in sorted(grouped.items()):
                chunks.append('<details><summary>'+e(tr(status))+' · '+e(tr('cat_'+category))+' · '+str(len(targets))+'</summary><p>'+e(tool)+'</p><ul>')
                chunks.extend('<li>'+e(target)+'</li>' for target in sorted(targets))
                chunks.append('</ul></details>')
        chunks.append('</section>')
    chunks.append('<h2>'+e(tr('technical_details'))+'</h2><p>'+e(format_timestamp(report.started)+' → '+format_timestamp(report.finished))+'</p>')
    resources=getattr(report,'resource_details',[])
    chunks.append('<h3>'+e(tr('page_resources'))+'</h3><p>'+e(tr('resource_method'))+'</p>')
    for type_ in ('html','css','javascript','image','font','fetch','other'):
        items=[r for r in resources if r.get('type','other')==type_]
        if not items:continue
        chunks.append('<details><summary>'+e(tr('type_'+type_))+' · '+str(len(items))+'</summary><div class="table"><table><tr>'+''.join('<th>'+e(tr(key))+'</th>' for key in ('report_target','http_status','target_scope','source_location','report_status'))+'</tr>')
        for item in items:
            sources='; '.join(ref['source']+(' : '+str(ref['line']) if ref.get('line') else '') for ref in item.get('references',[])) or '—'
            status=tr('resource_checked' if item['checked'] else 'not_checked')
            chunks.append('<tr>'+''.join('<td>'+e(value)+'</td>' for value in (item['target'],item.get('http_status') or '—',tr('scope_'+item['scope']),sources,status))+'</tr>')
        chunks.append('</table></div></details>')
    chunks.append('<h3>'+e(tr('tools'))+'</h3><div class="table"><table><tr>'+''.join('<th>'+e(tr(key))+'</th>' for key in ('tool_name','tool_version','report_status'))+'</tr>')
    for tool in report.tools:
        chunks.append('<tr>'+''.join('<td>'+e(value)+'</td>' for value in (tool['name'],tool.get('version') or '—',tr('available' if tool['available'] else 'unavailable')))+'</tr>')
    chunks.append('</table></div>')
    for label,data in [('options',report.options),('tools',report.tools),('checks',report.checks),('resource_details',getattr(report,'resource_details',[]))]:
        chunks.append('<details><summary>'+e(tr(label))+'</summary><pre>'+e(json.dumps(data,ensure_ascii=False,indent=2))+'</pre></details>')
    chunks.append('</body></html>')
    return ''.join(chunks).replace('</head>',watermark_style()+'</head>',1)


def save_report(report,path,language='de'):
    path=Path(path)
    if path.suffix.lower()=='.json':text=json.dumps(report.data(),ensure_ascii=False,indent=2)
    elif path.suffix.lower() in ('.html','.htm'):text=html_report(report,language)
    else:raise ValueError('Use .html or .json')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.checkweb-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:out.write(text)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
