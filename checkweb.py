#!/usr/bin/env python3
"""checkweb – local and online website diagnostics. GPL-3.0-only."""
import argparse
import json
import logging
from pathlib import Path
import sys
from modules.model import VERSION,settings,config_dir,CATEGORIES,tools_available


def main():
    parser=argparse.ArgumentParser(description='checkweb – GTK 4 website diagnostics / Webseitenprüfung')
    parser.add_argument('--version',action='version',version=f'checkweb {VERSION}')
    parser.add_argument('--author',action='store_true')
    parser.add_argument('--tools',action='store_true',help='List supported installed tools')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--local',metavar='DIRECTORY',help='Run a local scan without GUI')
    group.add_argument('--url',help='Run an online scan without GUI')
    parser.add_argument('--checks',help='Comma-separated check names')
    parser.add_argument('--output',help='Write .html or .json report')
    parser.add_argument('--language',choices=['de','en'],default=None)
    parser.add_argument('--no-network',action='store_true',help='Disable external link probes for local scans')
    parser.add_argument('--max-pages',type=int)
    args=parser.parse_args()
    if args.author:print('Josef');return 0
    if args.tools:print(json.dumps(tools_available(),ensure_ascii=False,indent=2));return 0
    from modules.lifecycle import execute_logged
    mode = 'CLI lokal' if args.local else 'CLI online' if args.url else 'GUI'
    return execute_logged(lambda: run_application(args, parser), mode)


def run_application(args, parser):
    for tool in tools_available():
        if not tool['available']:
            logging.warning('Werkzeug fehlt / Missing tool: %s (APT: %s)%s',tool['name'],tool['package'],
                '; optional, not used by the current HTML checker (html5lib)' if tool['name']=='tidy' else '')
    if args.local or args.url:
        from modules.engine import Scanner
        from modules.reports import save_report
        opts=settings()
        if args.checks:
            selected=args.checks.split(',')
            if not set(selected)<=set(CATEGORIES):parser.error('Unknown checks. Choose: '+','.join(CATEGORIES))
            opts['categories']=selected
        if args.no_network:
            if args.url:parser.error('--no-network is only available with --local')
            opts['external_links']=False
        if args.max_pages is not None:
            if not 0<=args.max_pages<=10000:parser.error('--max-pages must be 0..10000 (0 = unlimited)')
            opts['max_pages']=args.max_pages
        scanner=Scanner('local' if args.local else 'online',args.local or args.url,opts)
        try:report=scanner.run()
        except KeyboardInterrupt:scanner.cancel.set();return 130
        if args.output:save_report(report,args.output,args.language or opts['language'])
        else:print(json.dumps(report.data(),ensure_ascii=False,indent=2))
        return 2 if report.status in ('failed','incomplete') else 1 if any(f.severity=='error' for f in report.findings) else 0
    try:
        from modules.gui import App
        return App().run([sys.argv[0]])
    except (ImportError,ValueError) as exc:
        print('GTK 4/PyGObject required: python3-gi gir1.2-gtk-4.0\n'+str(exc),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
