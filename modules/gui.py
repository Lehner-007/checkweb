"""GTK 4 interface; scanning and downloads run off the main thread."""
import json
import logging
import threading
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,Gio,GLib,Pango
from .model import CATEGORIES,VERSION,settings,config_dir,atomic_json,tools_available
from .i18n import Strings
from .engine import Scanner, normalize_url_input, canonical
from .reports import SECTIONS, save_report, group_findings, finding_section, limit_messages, incomplete_messages, format_duration
from .languages import import_pack,download_pack,download_version,ProgramIdentityError

class Window(Gtk.ApplicationWindow):
    def __init__(self,app):
        super().__init__(application=app,title=f'checkweb {VERSION}')
        self.set_default_size(1120,790)
        self.opts=settings()
        self.tr=Strings(self.opts['language'])
        if self.tr.code.split('-')[0] in ('ar','he','fa','ur'):Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        self.report=None
        self.worker=None
        self.cancel_event=threading.Event()
        self.page=0
        self.dialogs=[]
        self.closing=False
        self.connect('close-request',self.close_request)
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        for method in ('set_margin_top','set_margin_bottom','set_margin_start','set_margin_end'):getattr(outer,method)(14)
        self.set_child(outer)
        self.menu_actions={}
        outer.append(self.build_menu())
        top=Gtk.Box(spacing=10)
        subtitle=Gtk.Label(label=self.tr('app_subtitle'),xalign=0,hexpand=True)
        top.append(subtitle)
        outer.append(top)
        targetrow=Gtk.Box(spacing=8)
        self.mode=Gtk.DropDown.new_from_strings([self.tr('local'),self.tr('online')])
        self.mode.connect('notify::selected',self.mode_changed)
        self.target=Gtk.Entry(hexpand=True,placeholder_text='/home/… / https://…')
        self.target.set_direction(Gtk.TextDirection.LTR)
        self.clear_target_button=self.button('clear_target',self.clear_target)
        self.clear_target_button.set_sensitive(False)
        self.target.connect('changed',lambda entry:self.clear_target_button.set_sensitive(bool(entry.get_text()) and self.target.get_sensitive()))
        self.folder=self.button('browse',self.choose_folder)
        targetrow.append(self.mode);targetrow.append(self.target);targetrow.append(self.clear_target_button);targetrow.append(self.folder)
        outer.append(targetrow)
        self.pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,wide_handle=True,vexpand=True)
        outer.append(self.pane)
        left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        header=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        header.append(Gtk.Label(label=self.tr('checks'),hexpand=True,xalign=0))
        header.append(self.button('select_all_checks',lambda *_:self.select_all(True)))
        header.append(self.button('clear_checks',lambda *_:self.select_all(False)))
        left.append(header)
        self.checkboxes={}
        capabilities={x['category']:x for x in tools_available()}
        missing=[x['package'] for x in capabilities.values() if not x['available']]
        self.tool_notice=Gtk.Label(label=self.tr('missing_tools',packages=', '.join(missing)) if missing else '',wrap=True,xalign=0)
        self.tool_notice.set_visible(bool(missing))
        outer.append(self.tool_notice)
        for category in CATEGORIES:
            available=capabilities.get(category,{}).get('available',True)
            box=Gtk.CheckButton(label=self.tr('cat_'+category))
            box.set_active(category in self.opts['categories'] and available)
            box.set_sensitive(available)
            if not available:box.set_tooltip_text(self.tr('unavailable')+': '+capabilities[category]['package'])
            self.checkboxes[category]=box
            left.append(box)
        notes=Gtk.Label(label=self.tr('limits_note'),wrap=True,xalign=0,max_width_chars=32)
        notes.add_css_class('dim-label');left.append(notes)
        lscroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,min_content_width=265)
        lscroll.set_child(left);self.pane.set_start_child(lscroll);self.pane.set_position(285)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        filters=Gtk.Box(spacing=8)
        self.severity=Gtk.DropDown.new_from_strings([self.tr(x) for x in ('all','error','warning','info')])
        self.severity.connect('notify::selected',self.filter_changed)
        self.search=Gtk.SearchEntry(hexpand=True,placeholder_text=self.tr('filter'))
        self.search.connect('search-changed',self.filter_changed)
        filters.append(self.severity);filters.append(self.search);right.append(filters)
        self.summary=Gtk.Label(label=self.tr('ready'),xalign=0,wrap=True)
        right.append(self.summary)
        self.coverage=Gtk.Label(xalign=0,wrap=True)
        self.coverage.add_css_class('dim-label');right.append(self.coverage)
        self.listbox=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.connect('row-selected',self.row_selected)
        scroll=Gtk.ScrolledWindow(vexpand=True,min_content_height=170)
        scroll.set_child(self.listbox)
        results=Gtk.Overlay(vexpand=True)
        background=Gtk.Box();background.add_css_class('view')
        results.set_child(background)
        image=Path(__file__).resolve().parent.parent/'assets'/'report_watermark.png'
        self.watermark=Gtk.Picture.new_for_filename(str(image))
        self.watermark.set_can_shrink(True)
        self.watermark.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.watermark.set_opacity(0.10)
        self.watermark.set_can_target(False)
        self.watermark.set_focusable(False)
        for edge in ('top','bottom','start','end'):getattr(self.watermark,'set_margin_'+edge)(20)
        results.add_overlay(self.watermark)
        results.set_measure_overlay(self.watermark,False)
        self.listbox.add_css_class('checkweb-results')
        css=Gtk.CssProvider()
        css.load_from_data(b'list.checkweb-results { background-color: transparent; }')
        self.listbox.get_style_context().add_provider(css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        results.add_overlay(scroll)
        results.set_measure_overlay(scroll,True)
        right.append(results)
        nav=Gtk.Box(spacing=8)
        self.prev=self.button('previous',lambda *_:self.change_page(-1));nav.append(self.prev)
        self.page_label=Gtk.Label(hexpand=True);nav.append(self.page_label)
        self.next=self.button('next',lambda *_:self.change_page(1));nav.append(self.next)
        right.append(nav)
        self.detail=Gtk.TextView(editable=False,cursor_visible=False,wrap_mode=Gtk.WrapMode.WORD_CHAR)
        ds=Gtk.ScrolledWindow(min_content_height=150);ds.set_child(self.detail);right.append(ds)
        self.pane.set_end_child(right)
        action=Gtk.Box(spacing=8)
        self.start_button=self.button('start',self.start_scan);action.append(self.start_button)
        self.cancel_button=self.button('cancel',self.cancel_scan);self.cancel_button.set_sensitive(False);action.append(self.cancel_button)
        self.export_button=self.button('export',self.export);self.export_button.set_sensitive(False);action.append(self.export_button)
        self.status=Gtk.Label(label=self.tr('ready'),xalign=0,hexpand=True,ellipsize=Pango.EllipsizeMode.MIDDLE)
        action.append(self.status);outer.append(action)
        self.progress=Gtk.ProgressBar(show_text=False);outer.append(self.progress)
        self.render()
        GLib.timeout_add(180,self.pulse)
        GLib.idle_add(self.auto_update)

    def build_menu(self):
        menu=Gio.Menu()
        groups=[('menu_file',[('browse',self.choose_folder),('export',self.export),('quit',lambda *_:self.close())]),
                ('checks',[('start',self.start_scan),('cancel',self.cancel_scan),('all',lambda *_:self.select_all(True)),('none',lambda *_:self.select_all(False))]),
                ('menu_options',[('tools',self.show_tools),('settings',self.show_settings),('log',self.show_log)]),
                ('help',[('help',self.show_help),('about',self.show_about)])]
        for label,entries in groups:
            submenu=Gio.Menu()
            for key,callback in entries:
                action=Gio.SimpleAction.new(key,None)
                action.connect('activate',lambda a,p,fn=callback:fn())
                self.add_action(action);self.menu_actions[key]=action
                submenu.append(self.tr({'all':'select_all_checks','none':'clear_checks','help':'open_help'}.get(key,key)),'win.'+key)
            menu.append_submenu(self.tr(label),submenu)
        for key in ('export','cancel'):self.menu_actions[key].set_enabled(False)
        return Gtk.PopoverMenuBar.new_from_model(menu)

    def button(self,key,callback):
        b=Gtk.Button(label=self.tr(key));b.connect('clicked',callback);return b

    def clear_target(self,*_):
        self.target.set_text('')
        self.target.grab_focus()

    def mode_changed(self,*_):
        if not hasattr(self,'folder'):return
        online=self.mode.get_selected()==1
        self.folder.set_sensitive(not online)
        self.menu_actions['browse'].set_enabled(not online)
        self.target.set_placeholder_text('https://example.org' if online else '/home/…')
        if online and not self.target.get_text().strip():self.target.set_text('https://')
        elif not online and self.target.get_text().strip()=='https://':self.target.set_text('')
        self.checkboxes['php'].set_sensitive(not online and any(x['name']=='php' and x['available'] for x in tools_available()))

    def select_all(self,on):
        for c in self.checkboxes.values():
            if c.get_sensitive():c.set_active(on)

    def file_dialog(self,key,action,callback,start=None):
        dialog=Gtk.FileChooserNative(title=self.tr(key),transient_for=self,modal=True,
            action=action,accept_label=self.tr('save' if action==Gtk.FileChooserAction.SAVE else key),cancel_label=self.tr('cancel'))
        # NativeDialog is not a widget owned by the window. Keep it alive until response.
        self.dialogs.append(dialog)
        folder=Path(start).expanduser() if start else Path.home()
        if not folder.is_dir():folder=Path.home()
        try:dialog.set_current_folder(Gio.File.new_for_path(str(folder)))
        except GLib.Error:logging.exception('Cannot set file chooser directory')
        def response(d,r):
            try:
                if r==Gtk.ResponseType.ACCEPT:
                    file=d.get_file()
                    path=file.get_path() if file else None
                    if not path:raise ValueError(self.tr('local_path_required'))
                    callback(Path(path),d)
            except (OSError,ValueError,GLib.Error) as exc:
                logging.exception('File dialog operation failed')
                self.notify(self.background_error(exc),self.tr('error_title'))
            finally:
                d.destroy()
                if d in self.dialogs:self.dialogs.remove(d)
        dialog.connect('response',response)
        return dialog

    def choose_folder(self,*_):
        def selected(path,dialog):
            if not path.is_dir():raise ValueError(self.tr('folder_invalid'))
            self.target.set_text(str(path))
        dialog=self.file_dialog('browse',Gtk.FileChooserAction.SELECT_FOLDER,selected,self.target.get_text().strip() or None)
        dialog.show()

    def notify(self,text,title=None):
        dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.INFO,buttons=Gtk.ButtonsType.CLOSE,text=title or 'checkweb',secondary_text=str(text))
        dialog.connect('response',lambda d,r:d.destroy());dialog.present()

    def question(self,text,yes):
        dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,buttons=Gtk.ButtonsType.NONE,text=text)
        dialog.add_button(self.tr('no'),Gtk.ResponseType.NO);dialog.add_button(self.tr('yes'),Gtk.ResponseType.YES)
        def response(d,r):
            d.destroy()
            if r==Gtk.ResponseType.YES:yes()
        dialog.connect('response',response);dialog.present()

    def start_scan(self,*_):
        if self.worker and self.worker.is_alive():return
        target=self.target.get_text().strip()
        categories=[k for k,b in self.checkboxes.items() if b.get_sensitive() and b.get_active()]
        if not target or not categories:self.notify(self.tr('no_selection'));return
        if self.mode.get_selected()==1:
            try:target=canonical(normalize_url_input(target))
            except ValueError:self.notify(self.tr('invalid_url'));return
            self.target.set_text(target)
        self.opts['categories']=categories
        self.cancel_event=threading.Event()
        self.report=None;self.render()
        self.set_running(True)
        mode='local' if self.mode.get_selected()==0 else 'online'
        self.worker=threading.Thread(target=self.scan_worker,args=(mode,target,self.opts.copy()),daemon=True)
        self.worker.start()

    def set_running(self,running):
        for w in (self.start_button,self.target,self.mode):w.set_sensitive(not running)
        self.folder.set_sensitive(not running and self.mode.get_selected()==0)
        for key in ('start','settings'):self.menu_actions[key].set_enabled(not running)
        self.menu_actions['browse'].set_enabled(not running and self.mode.get_selected()==0)
        self.menu_actions['cancel'].set_enabled(running)
        self.menu_actions['export'].set_enabled(not running and self.report is not None)
        self.clear_target_button.set_sensitive(not running and bool(self.target.get_text()))
        self.cancel_button.set_sensitive(running)
        self.export_button.set_sensitive(not running and self.report is not None)
        self.status.set_label(self.tr('running' if running else self.report.status if self.report else 'ready'))

    def scan_worker(self,mode,target,opts):
        try:
            callback=lambda n,t:GLib.idle_add(self.update_progress,n,t)
            if opts['timeout']==0:
                from .scanprocess import run_interruptible
                report=run_interruptible(mode,target,opts,callback,self.cancel_event)
            else:
                scanner=Scanner(mode,target,opts,callback,self.cancel_event)
                report=scanner.run()
            GLib.idle_add(self.scan_done,report)
        except Exception as exc:
            logging.exception('Scan worker failed')
            GLib.idle_add(self.worker_error,str(exc))

    def worker_error(self,text):
        self.set_running(False);self.notify(text,self.tr('error_title'));return False

    def update_progress(self,n,target):
        if not self.closing:self.status.set_label(self.tr('progress',count=n,target=target))
        return False

    def scan_done(self,report):
        self.report=report
        self.page=0
        self.set_running(False)
        self.progress.set_fraction(0 if report.status!='complete' else 1)
        self.render()
        if self.closing:self.destroy()
        return False

    def pulse(self):
        if self.worker and self.worker.is_alive():self.progress.pulse()
        return not self.closing

    def cancel_scan(self,*_):
        self.cancel_event.set();self.cancel_button.set_sensitive(False)
        self.menu_actions['cancel'].set_enabled(False)

    def filter_changed(self,*_):self.page=0;self.render()
    def change_page(self,n):self.page=max(0,self.page+n);self.render()

    def render(self):
        child=self.listbox.get_first_child()
        while child:
            nxt=child.get_next_sibling();self.listbox.remove(child);child=nxt
        findings=self.report.findings if self.report else []
        counts=Counter(finding_section(f) for f in findings)
        self.summary.set_label(self.tr('finding_summary',**{section:counts[section] for section in SECTIONS}))
        executed=sum(c['status']=='done' for c in self.report.checks) if self.report else 0
        skipped=sum(c['status']!='done' for c in self.report.checks) if self.report else 0
        coverage=self.tr('coverage',done=executed,skipped=skipped)
        if self.report:
            resources=self.report.resource_counts
            if resources:coverage=self.tr('resource_summary',found=resources['found'],checked=resources['checked'],unchecked=resources['unchecked'])+'\n'+coverage
            coverage+=' · '+self.tr('report_duration')+': '+format_duration(self.report)
            limits=incomplete_messages(self.report,self.tr)
            if limits:coverage=self.tr('incomplete').upper()+'\n'+'\n'.join(limits)+'\n'+coverage
        self.coverage.set_label(coverage)
        selected=('all','error','warning','info')[self.severity.get_selected()]
        query=self.search.get_text().casefold()
        filtered=[f for f in findings if (selected=='all' or f.severity==selected) and (not query or query in (f.target+' '+f.detail+' '+self.tr('msg_'+f.code)+' '+self.tr('cat_'+f.category)).casefold())]
        filtered=group_findings(filtered)
        pages=max(1,(len(filtered)+99)//100);self.page=min(self.page,pages-1)
        self.page_label.set_label(self.tr('page',page=self.page+1,pages=pages));self.prev.set_sensitive(self.page>0);self.next.set_sensitive(self.page+1<pages)
        if not filtered:self.listbox.append(Gtk.Label(label=self.tr('no_results'),wrap=True,margin_top=20,margin_bottom=20))
        for group in filtered[self.page*100:(self.page+1)*100]:
            f=group[0]
            row=Gtk.ListBoxRow();row.finding=f;row.findings=group
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3,margin_top=7,margin_bottom=7,margin_start=8,margin_end=8)
            first=Gtk.Label(label=self.tr('section_'+finding_section(f))+' · '+self.tr('cat_'+f.category)+' · '+self.tr('scope_'+(f.scope or 'unknown'))+' — '+self.tr('msg_'+f.code),xalign=0,wrap=True)
            second=Gtk.Label(label=self.tr('occurrences',count=len(group))+' · '+f.target+(f' : {f.line}' if f.line else ''),xalign=0,ellipsize=Pango.EllipsizeMode.MIDDLE)
            second.add_css_class('dim-label');box.append(first);box.append(second);row.set_child(box);self.listbox.append(row)
        self.detail.get_buffer().set_text('')

    def row_selected(self,box,row):
        if not row or not hasattr(row,'finding'):return
        f=row.finding
        text='\n'.join((self.tr('msg_'+f.code),f.target,self.tr('line')+': '+str(f.line or '—'),self.tr('detail')+': '+f.detail,self.tr('suggestion')+': '+self.tr('fix_'+f.code),self.tr('tool_name')+': '+f.tool))
        text+='\n'+self.tr('report_target')+': '+(f.destination or f.target)+'\n'+self.tr('target_scope')+': '+self.tr('scope_'+(f.scope or 'unknown'))
        if f.link_text:text+='\n'+self.tr('link_text')+': '+f.link_text
        if f.resource_type:text+='\n'+self.tr('resource_type')+': '+self.tr('type_'+f.resource_type)
        if f.http_status:text+='\nHTTP: '+str(f.http_status)
        if len(row.findings)>1:
            text+='\n\n'+'\n\n'.join(item.target+' : '+str(item.line or '—')+'\n'+item.detail for item in row.findings)
        self.detail.get_buffer().set_text(text)

    def export(self,*_):
        if not self.report:return
        report=self.report
        def selected(path,dialog):
            if not path.suffix:
                chosen=dialog.get_filter()
                path=path.with_suffix('.json' if chosen and chosen.get_name()=='JSON' else '.html')
            if path.suffix.lower() not in ('.html','.htm','.json'):
                raise ValueError(self.tr('report_extension'))
            def save():
                try:
                    save_report(report,path,self.tr.code)
                    self.report_directory=path.parent
                    self.notify(self.tr('saved',path=path))
                except (OSError,ValueError) as exc:
                    logging.exception('Report export failed')
                    self.notify(self.background_error(exc),self.tr('error_title'))
            if path.exists():self.question(self.tr('confirm_overwrite'),save)
            else:save()
        dialog=self.file_dialog('export',Gtk.FileChooserAction.SAVE,selected,getattr(self,'report_directory',None))
        dialog.set_current_name('checkweb-report.html')
        for ext in ('html','json'):
            fil=Gtk.FileFilter();fil.set_name(ext.upper());fil.add_pattern('*.'+ext);dialog.add_filter(fil)
        dialog.show()

    def show_help(self,*_):
        Gio.AppInfo.launch_default_for_uri(self.tr.help_path().as_uri(),None)

    def show_tools(self,*_):
        lines=[]
        for tool in tools_available():
            lines.append(tool['name']+' — '+self.tr('available' if tool['available'] else 'unavailable')+'\n'+tool.get('version','')+'\nAPT: '+tool['package'])
        lines.append(self.tr('tidy_note'))
        self.notify('\n\n'.join(lines),self.tr('tools'))

    def show_log(self,*_):
        from .logfile import read_log,save_log,LogChangedError
        path=config_dir()/'logs'/'checkweb.log'
        window=Gtk.Window(title=self.tr('log'),transient_for=self,default_width=780,default_height=500)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10,margin_top=12,margin_bottom=12,margin_start=12,margin_end=12)
        window.set_child(box)
        box.append(Gtk.Label(label=str(path),xalign=0,wrap=True,selectable=True))
        box.append(Gtk.Label(label=self.tr('log_help'),xalign=0,wrap=True))
        view=Gtk.TextView(monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR,vexpand=True)
        view.set_name('log_editor')
        scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(view);box.append(scroll)
        state={'bytes':b''}
        def reload():
            try:
                state['bytes']=read_log(path)
                view.get_buffer().set_text(state['bytes'].decode('utf-8',errors='replace'))
                view.get_buffer().set_modified(False)
            except OSError as exc:self.notify(self.background_error(exc),self.tr('error_title'))
        def request_reload(*_):
            if view.get_buffer().get_modified():self.question(self.tr('discard_log'),reload)
            else:reload()
        def save(*_):
            buffer=view.get_buffer()
            try:
                state['bytes']=save_log(path,buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True),state['bytes'])
                buffer.set_modified(False)
                status.set_label(self.tr('log_saved'))
            except LogChangedError:self.notify(self.tr('log_changed'),self.tr('error_title'))
            except OSError as exc:self.notify(self.background_error(exc),self.tr('error_title'))
        def close(*_):
            if view.get_buffer().get_modified():
                self.question(self.tr('discard_log'),window.destroy)
                return True
            return False
        status=Gtk.Label(xalign=0,wrap=True);box.append(status)
        buttons=Gtk.Box(spacing=8)
        buttons.append(self.button('reload_log',request_reload));buttons.append(self.button('save_log',save))
        buttons.append(self.button('close',lambda *_:window.close()));box.append(buttons)
        window.connect('close-request',close)
        reload();window.present()
        return window

    def show_settings(self,*_):
        window=Gtk.Window(title=self.tr('settings'),transient_for=self,modal=True,default_width=650,default_height=620)
        layout=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        window.set_child(layout)
        scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  vscrollbar_policy=Gtk.PolicyType.ALWAYS)
        layout.append(scroll)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10,margin_top=16,margin_bottom=16,margin_start=16,margin_end=16)
        scroll.set_child(box)
        controls={}
        def label(key):
            widget=Gtk.Label(label=self.tr(key),xalign=0,wrap=True)
            box.append(widget)
        def group(key):
            box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
            label(key)
        codes=Strings.languages()
        lang=Gtk.DropDown.new_from_strings([{'de':'Deutsch','en':'English'}.get(code,code) for code in codes])
        lang.set_selected(codes.index(self.tr.code) if self.tr.code in codes else codes.index('en'))
        label('language');box.append(lang)
        group('scan_settings')
        label('zero_limits')
        for key,low,high in [('max_pages',0,10000),('max_depth',0,20),('max_resources',0,50000),('timeout',0,60)]:
            row=Gtk.Box(spacing=8)
            row.append(Gtk.Label(label=self.tr(key),xalign=0,hexpand=True,wrap=True))
            spin=Gtk.SpinButton.new_with_range(low,high,1)
            spin.set_name(key);spin.set_value(self.opts[key]);controls[key]=spin
            row.append(spin);box.append(row)
        for key in ('external_links','robots'):
            control=Gtk.CheckButton(label=self.tr(key));control.set_active(self.opts[key]);controls[key]=control;box.append(control)
        group('update_settings')
        control=Gtk.CheckButton(label=self.tr('update_check'));control.set_active(self.opts['update_check'])
        controls['update_check']=control;box.append(control)
        label('update_interval_label')
        interval=Gtk.Box(spacing=8)
        interval.append(Gtk.Label(label=self.tr('every')))
        spin=Gtk.SpinButton.new_with_range(1,365,1);spin.set_name('update_interval_value')
        spin.set_value(self.opts['update_interval_value']);controls['update_interval_value']=spin;interval.append(spin)
        units=('days','weeks','months')
        unit=Gtk.DropDown.new_from_strings([self.tr(x) for x in units])
        unit.set_selected(units.index(self.opts['update_interval_unit']) if self.opts['update_interval_unit'] in units else 1)
        interval.append(unit);box.append(interval)
        label('update_interval_help')
        label('update_url')
        controls['update_url']=Gtk.Entry(text=self.opts['update_url']);box.append(controls['update_url'])
        box.append(self.button('update_now',lambda *_:self.check_update(controls['update_url'].get_text())))
        group('language_extensions')
        label('source_url')
        controls['source_url']=Gtk.Entry(text=self.opts['source_url']);box.append(controls['source_url'])
        box.append(self.button('import_language',self.import_language))
        box.append(self.button('download_language',lambda *_:self.download_language(controls['source_url'].get_text())))
        def save(*_):
            new=self.opts.copy()
            for key,control in controls.items():
                if isinstance(control,Gtk.SpinButton):
                    control.update()
                    new[key]=control.get_value_as_int()
                else:new[key]=control.get_active() if isinstance(control,Gtk.CheckButton) else control.get_text().strip()
            new['language']=codes[lang.get_selected()];new['update_interval_unit']=units[unit.get_selected()]
            try:
                old=config_dir()/'settings.json'
                if old.is_file():
                    try:json.loads(old.read_text('utf-8'))
                    except (ValueError,UnicodeError):
                        import shutil,time
                        shutil.copy2(old,old.with_name('settings.invalid.'+str(time.time_ns())+'.json'))
                atomic_json(old,new)
                self.opts=new;window.destroy()
                if new['language']!=self.tr.code:self.notify(self.tr('restart_language'))
            except OSError as e:self.notify(str(e),self.tr('error_title'))
        layout.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        footer=Gtk.Box(spacing=10,halign=Gtk.Align.END,margin_top=12,margin_bottom=12,margin_start=16,margin_end=16)
        footer.append(self.button('cancel',lambda *_:window.destroy()))
        footer.append(self.button('save_settings',save))
        layout.append(footer)
        window.present()
        return window

    def show_about(self,*_):
        dialog=Gtk.AboutDialog(transient_for=self,modal=True,program_name='checkweb',version=VERSION,
                               comments=self.tr('app_subtitle'),authors=['Josef'],license_type=Gtk.License.GPL_3_0_ONLY)
        image=Path(__file__).resolve().parent.parent/'assets'/'checkweb.png'
        if image.is_file():
            from gi.repository import Gdk
            dialog.set_logo(Gdk.Texture.new_from_filename(str(image)))
        dialog.present()
        return dialog

    def background_error(self,exc):
        return self.tr('wrong_program') if isinstance(exc,ProgramIdentityError) else str(exc)

    def background(self,fn,done,quiet=False):
        def run():
            try:
                result=fn()
                def deliver():
                    try: done(result)
                    except Exception as exc: self.notify(self.background_error(exc),self.tr('error_title'))
                    return False
                GLib.idle_add(deliver)
            except Exception as exc:
                text=self.background_error(exc)
                if not quiet:GLib.idle_add(lambda:(self.notify(text,self.tr('error_title')),False)[1])
        threading.Thread(target=run,daemon=True).start()

    def import_language(self,*_):
        def selected(path,dialog):
            self.background(lambda:import_pack(path),lambda code:self.notify(self.tr('language_installed',code=code)))
        dialog=self.file_dialog('import_language',Gtk.FileChooserAction.OPEN,selected)
        fil=Gtk.FileFilter();fil.set_name('JSON');fil.add_pattern('*.json');dialog.add_filter(fil)
        dialog.show()

    def download_language(self,source):
        if not source.strip():self.notify(self.tr('no_source'));return
        dialog=Gtk.Dialog(title=self.tr('download_language'),transient_for=self,modal=True)
        entry=Gtk.Entry(placeholder_text=self.tr('language_code'));dialog.get_content_area().append(entry)
        dialog.add_button(self.tr('cancel'),Gtk.ResponseType.CANCEL);dialog.add_button(self.tr('download_language'),Gtk.ResponseType.OK)
        def response(d,r):
            code=entry.get_text().strip();d.destroy()
            if r==Gtk.ResponseType.OK:self.background(lambda:download_pack(source,code),lambda result:self.notify(self.tr('language_installed',code=result)))
        dialog.connect('response',response);dialog.present()

    def check_update(self,url,automatic=False):
        if not url:
            if not automatic:self.notify(self.tr('no_source'))
            return
        def done(latest):
            self.opts['last_update_check']=datetime.now(timezone.utc).isoformat()
            atomic_json(config_dir()/'settings.json',self.opts)
            if not automatic or latest!=VERSION:self.notify(self.tr('version_result',current=VERSION,latest=latest))
        self.background(lambda:download_version(url),done,quiet=automatic)

    def auto_update(self):
        if not self.opts['update_check'] or not self.opts['update_url']:return False
        try:last=datetime.fromisoformat(self.opts['last_update_check'])
        except ValueError:last=datetime(1970,1,1,tzinfo=timezone.utc)
        if last.tzinfo is None:last=last.replace(tzinfo=timezone.utc)
        days={'days':1,'weeks':7,'months':30}.get(self.opts['update_interval_unit'],7)*self.opts['update_interval_value']
        if datetime.now(timezone.utc)-last>=timedelta(days=days):self.check_update(self.opts['update_url'],True)
        return False

    def close_request(self,*_):
        if self.worker and self.worker.is_alive():
            def stop():self.closing=True;self.cancel_scan()
            self.question(self.tr('confirm_close'),stop);return True
        for dialog in self.dialogs[:]:dialog.destroy()
        self.dialogs.clear()
        return False

class App(Gtk.Application):
    def __init__(self):super().__init__(application_id='eu.josef.checkweb',flags=Gio.ApplicationFlags.NON_UNIQUE)
    def do_activate(self):
        window=self.get_active_window()
        if window is None:window=Window(self)
        window.present()
