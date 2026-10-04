"""Exercise native chooser lifetime and responses on the real GTK display."""
import gc
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from modules.gui import App,Window,Gtk,GLib,Gio
from modules.model import Report,tools_available,DEFAULTS,atomic_json,config_dir

with tempfile.TemporaryDirectory(prefix='checkweb-dialogs-') as tmp:
    root=Path(tmp)
    os.environ.pop('CHECKWEB_DEV',None)
    for key in ('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME'):os.environ[key]=str(root/key)
    os.environ['GSETTINGS_BACKEND']='memory'
    os.environ['GIO_USE_VFS']='local'
    atomic_json(config_dir()/'settings.json',dict(DEFAULTS,language=os.environ.get('CHECKWEB_LANGUAGE','de')))
    app=App();app.register(None)
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',bool(os.environ.get('CHECKWEB_DARK')))
    caps=tools_available()
    for tool in caps:
        if tool['name']=='tidy':tool['available']=False
    with patch('modules.gui.tools_available',return_value=caps):window=Window(app)
    window.present()
    notices=[]
    window.notify=lambda text,title=None:notices.append(str(text))
    errors=[]
    def pause():
        for _ in range(5):yield
    def scenario():
        yield from pause()
        assert 'tidy' in window.tool_notice.get_label()
        assert window.tool_notice.get_visible()
        assert isinstance(window.get_child().get_first_child(),Gtk.PopoverMenuBar)
        window.mode.set_selected(1)
        assert window.target.get_text()=='https://'
        assert not window.menu_actions['browse'].get_enabled()
        window.mode.set_selected(0)
        assert not window.target.get_text()
        # Regression: the caller keeps no dialog reference while it is loading.
        window.menu_actions['browse'].activate(None)
        gc.collect();yield from pause()
        assert len(window.dialogs)==1 and window.dialogs[0].get_visible()
        d=window.dialogs[0];d.set_file(Gio.File.new_for_path(str(root)))
        yield from pause();d.emit('response',Gtk.ResponseType.ACCEPT)
        assert window.target.get_text()==str(root)
        assert not window.dialogs and window.get_visible()
        window.choose_folder();yield from pause()
        window.dialogs[0].emit('response',Gtk.ResponseType.CANCEL)
        assert window.target.get_text()==str(root) and not window.dialogs
        window.report=Report('local',str(root),[],status='complete')
        window.set_running(False)
        for ext in ('html','json'):
            window.menu_actions['export'].activate(None)
            gc.collect();yield from pause()
            d=window.dialogs[0];d.set_current_folder(Gio.File.new_for_path(str(root)))
            filters=d.get_filters();d.set_filter(filters.get_item(0 if ext=='html' else 1))
            d.set_current_name('report-'+ext)
            yield from pause();d.emit('response',Gtk.ResponseType.ACCEPT)
            output=root/('report-'+ext+'.'+ext)
            assert output.is_file(),notices
            if ext=='json':assert json.loads(output.read_text())['status']=='complete'
            else:assert output.read_text().startswith('<!doctype html>')
            assert not window.dialogs
        window.export();yield from pause()
        window.dialogs[0].emit('response',Gtk.ResponseType.CANCEL)
        assert not window.dialogs
        window.export();yield from pause()
        d=window.dialogs[0];d.set_current_folder(Gio.File.new_for_path(str(root)));d.set_current_name('bad.txt')
        yield from pause();d.emit('response',Gtk.ResponseType.ACCEPT)
        assert not (root/'bad.txt').exists()
        assert notices[-1]==window.tr('report_extension')
        window.set_default_size(800,600);yield from pause()
        assert window.menu_bar.get_allocated_width()>0
        window.set_running(True)
        assert not window.menu_actions['start'].get_enabled()
        assert not window.menu_actions['export'].get_enabled()
        window.cancel_scan();assert not window.menu_actions['cancel'].get_enabled()
        window.set_running(False)
        window.close()
        print('PASS: menu, HTTPS preset, missing tidy, chooser lifetime, folder select/cancel, HTML/JSON save/cancel, invalid extension, resize and action state')
    steps=scenario()
    def advance():
        try:next(steps)
        except StopIteration:app.quit();return False
        except Exception:
            import traceback
            errors.append(traceback.format_exc());app.quit();return False
        return True
    GLib.timeout_add(100,advance)
    app.run([])
    if errors:raise SystemExit('\n'.join(errors))
