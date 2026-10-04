"""Real GTK live language switch, preserving report and UI state."""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.model import ROOT,DEFAULTS
from modules.gui import App,Window
from modules.engine import Scanner
from modules.languages import import_pack
from gi.repository import Gtk,GLib

def walk(w):
    yield w
    child=w.get_first_child()
    while child:
        yield from walk(child)
        child=child.get_next_sibling()

def save_language(window,code):
    settings=window.show_settings()
    choice=next(w for w in walk(settings) if w.get_name()=='installed_languages')
    from modules.i18n import Strings
    choice.set_selected(Strings.languages().index(code))
    save=next(w for w in walk(settings) if isinstance(w,Gtk.Button) and w.get_label()==window.tr('save_settings'))
    save.emit('clicked')

with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp,'CHECKWEB_DEV':'0'}):
    for code in ('ar','fr'):import_pack(ROOT/'github/sprachpakete'/f'{code}.json')
    app=App();app.register(None)
    window=Window(app);window.present()
    site=Path(tmp)/'site';site.mkdir()
    (site/'index.html').write_text('<!doctype html><html lang="de"><head><title>Test</title></head><body><a href="missing.html">Broken</a></body></html>')
    opts=dict(DEFAULTS,categories=['links'],external_links=False)
    report=Scanner('local',str(site),opts).run()
    window.scan_done(report)
    window.target.set_text(str(site))
    window.checkboxes['css'].set_active(False)
    window.severity.set_selected(1)
    window.search.set_text('missing')
    window.render()
    row=window.listbox.get_row_at_index(0);window.listbox.select_row(row)
    finding=row.finding
    target_widget=window.target
    with patch.object(window,'notify',side_effect=AssertionError('No restart notification expected')):
        save_language(window,'en')
        assert window.tr.code=='en'
        from modules.lifecycle import log_text
        assert log_text('log_scan_worker')=='Scan worker failed'
        assert window.menu_actions['start'].get_enabled()
        assert window.mode.get_model().get_string(0)==window.tr('local')
        assert window.report is report and window.target is target_widget
        assert window.target.get_text()==str(site) and window.search.get_text()=='missing'
        assert window.severity.get_selected()==1 and not window.checkboxes['css'].get_active()
        assert window.listbox.get_selected_row().finding is finding
        assert window.menu_actions['export'].get_enabled()
        assert window.menu_bar.get_menu_model().get_item_attribute_value(0,'label',None).get_string()==window.tr('menu_file')
        assert any(isinstance(w,Gtk.Label) and w.get_label()==window.tr('app_subtitle') for w in walk(window))
        saved=json.loads((Path(tmp)/'checkweb/settings.json').read_text());assert saved['language']=='en'
        # Arabic -> French -> German, without restarting or replacing the window.
        for code,direction in [('ar',Gtk.TextDirection.RTL),('fr',Gtk.TextDirection.LTR),('de',Gtk.TextDirection.LTR)]:
            save_language(window,code)
            assert window.tr.code==code and window.get_direction()==direction
            assert log_text('log_scan_worker')==window.tr('log_scan_worker')
            assert window.target.get_direction()==Gtk.TextDirection.LTR
            assert window.report is report and window.target is target_widget
            assert window.menu_actions['start'].get_enabled()
        settings=window.show_settings()
        choice=next(w for w in walk(settings) if w.get_name()=='installed_languages')
        choice.set_selected(2)
        cancel=next(w for w in walk(settings) if isinstance(w,Gtk.Button) and w.get_label()==window.tr('cancel'))
        cancel.emit('clicked');assert window.tr.code=='de'
    window.destroy()
    print('GTK-Livewechsel DE/EN/AR/FR, Leserichtung, Menü, Bericht, Auswahl, Filter, Persistenz und Abbrechen geprüft.')
