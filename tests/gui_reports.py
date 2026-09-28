"""Real GTK regression for grouped findings, details and partial-scan status."""
import os
import tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from modules.gui import App,Window,GLib,Gtk
from modules.model import Report,Finding,DEFAULTS,atomic_json,config_dir

with tempfile.TemporaryDirectory(prefix='checkweb-report-gui-') as tmp:
    os.environ.pop('CHECKWEB_DEV',None)
    for key in ('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME'):os.environ[key]=tmp+'/'+key
    atomic_json(config_dir()/'settings.json',dict(DEFAULTS,language=os.environ.get('CHECKWEB_LANGUAGE','de')))
    app=App();app.register(None)
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',bool(os.environ.get('CHECKWEB_DARK')))
    window=Window(app);window.present()
    report=Report('online','https://example.invalid/',[],status='incomplete',limits={'max_resources':300})
    report.findings=[Finding('info','links',f'https://example.invalid/{i}','redirect','https://example.invalid/end') for i in range(100)]
    report.findings.extend([Finding('error','links','https://example.invalid/missing','http_missing','HTTP 404'),Finding('info','links','https://example.invalid/private','http_forbidden','HTTP 403'),Finding('info','system',report.target,'limit','max_resources')])
    window.report=report;window.set_running(False);window.render()
    errors=[]
    def check():
        try:
            window.target.set_text('https://example.invalid/')
            assert window.clear_target_button.get_sensitive()
            window.clear_target_button.emit('clicked')
            assert window.target.get_text()==''
            assert not window.clear_target_button.get_sensitive()
            window.target.set_text('/tmp/example')
            window.set_running(True)
            assert not window.clear_target_button.get_sensitive()
            window.set_running(False)
            window.clear_target_button.emit('clicked')
            assert window.target.get_text()==''
            assert window.listbox.get_row_at_index(3) is not None
            assert window.listbox.get_row_at_index(4) is None
            assert window.listbox.get_row_at_index(0).finding.code=='http_missing'
            assert window.status.get_label()==window.tr('incomplete')
            assert '300' in window.coverage.get_label()
            row=window.listbox.get_row_at_index(3)
            assert len(row.findings)==100
            window.listbox.select_row(row)
            buf=window.detail.get_buffer();text=buf.get_text(buf.get_start_iter(),buf.get_end_iter(),False)
            assert 'https://example.invalid/99' in text
            window.search.set_text('example.invalid/99');window.filter_changed()
            assert len(window.listbox.get_row_at_index(0).findings)==1
            window.search.set_text('');window.severity.set_selected(1);window.filter_changed()
            assert window.listbox.get_row_at_index(0).finding.code=='http_missing'
            assert window.listbox.get_row_at_index(1) is None
            print('PASS: grouped rows, all details, filtering, incomplete status and resource limit')
        except Exception:
            import traceback
            errors.append(traceback.format_exc())
        window.destroy();app.quit();return False
    GLib.timeout_add(600,check)
    app.run([])
    if errors:raise SystemExit('\n'.join(errors))
