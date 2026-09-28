"""Real GTK settings save/cancel, footer visibility and About regression."""
import os
import tempfile
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from modules.gui import App,Window,Gtk,GLib
from modules.model import config_dir,DEFAULTS,atomic_json

def widgets(widget):
    yield widget
    child=widget.get_first_child()
    while child:
        yield from widgets(child)
        child=child.get_next_sibling()

with tempfile.TemporaryDirectory(prefix='checkweb-settings-') as tmp:
    os.environ.pop('CHECKWEB_DEV',None)
    for key in ('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME'):os.environ[key]=tmp+'/'+key
    atomic_json(config_dir()/'settings.json',dict(DEFAULTS,language=os.environ.get('CHECKWEB_LANGUAGE','de')))
    app=App();app.register(None)
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',bool(os.environ.get('CHECKWEB_DARK')))
    w=Window(app);w.present();errors=[]
    def button(dialog,key):
        return next(x for x in widgets(dialog) if isinstance(x,Gtk.Button) and x.get_label()==w.tr(key))
    def spin(dialog,key):return next(x for x in widgets(dialog) if isinstance(x,Gtk.SpinButton) and x.get_name()==key)
    def pause():
        for _ in range(3):yield
    def scenario():
        d=w.show_settings();d.set_default_size(560,420);yield from pause()
        footer=d.get_child().get_last_child()
        ok,bounds=footer.compute_bounds(d)
        assert ok and bounds.get_y()>=0 and bounds.get_y()+bounds.get_height()<=d.get_height()
        scroll=d.get_child().get_first_child();adj=scroll.get_vadjustment()
        assert adj.get_upper()>adj.get_page_size()
        before=(config_dir()/'settings.json').read_bytes()
        spin(d,'max_pages').set_value(555)
        button(d,'cancel').emit('clicked')
        assert w.opts['max_pages']==100 and (config_dir()/'settings.json').read_bytes()==before
        d=w.show_settings();yield from pause()
        spin(d,'max_pages').set_text('234')
        interval=spin(d,'update_interval_value');interval.set_text('7')
        assert isinstance(interval.get_next_sibling(),Gtk.DropDown)
        interval.get_next_sibling().set_selected(2)
        button(d,'save_settings').emit('clicked')
        saved=json.loads((config_dir()/'settings.json').read_text())
        assert saved['max_pages']==234 and w.opts['max_pages']==234
        assert saved['update_interval_value']==7 and saved['update_interval_unit']=='months'
        d=w.show_settings();yield from pause()
        assert spin(d,'update_interval_value').get_value_as_int()==7
        d.close()
        d=w.show_settings();yield from pause()
        for key in ('max_pages','max_depth','max_resources','timeout'):spin(d,key).set_text('0')
        button(d,'save_settings').emit('clicked')
        saved=json.loads((config_dir()/'settings.json').read_text())
        assert all(saved[key]==0 for key in ('max_pages','max_depth','max_resources','timeout'))
        d=w.show_settings();yield from pause()
        assert all(spin(d,key).get_value_as_int()==0 for key in ('max_pages','max_depth','max_resources','timeout'))
        d.close()
        logpath=config_dir()/'logs/checkweb.log';logpath.parent.mkdir(exist_ok=True);logpath.write_text('before\n')
        assert 'log' in w.menu_actions
        log=w.show_log();log.set_default_size(560,420);yield from pause()
        view=next(x for x in widgets(log) if isinstance(x,Gtk.TextView))
        buffer=view.get_buffer()
        assert buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)=='before\n'
        buffer.set_text('edited\n')
        button(log,'save_log').emit('clicked')
        assert logpath.read_text()=='edited\n' and not buffer.get_modified()
        logpath.write_text('new entries\n')
        button(log,'reload_log').emit('clicked')
        assert buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)=='new entries\n'
        log.close()
        about=w.show_about();yield from pause()
        assert about.get_program_name()=='checkweb' and about.get_version()
        assert about.get_logo() is not None
        about.close()
        bar=w.get_child().get_first_child();model=bar.get_menu_model()
        help_menu=model.get_item_link(3,'submenu')
        assert help_menu.get_n_items()==2
        assert help_menu.get_item_attribute_value(0,'label',None).get_string()==w.tr('open_help')
        assert help_menu.get_item_attribute_value(1,'label',None).get_string()==w.tr('about')
        w.menu_actions['none'].activate(None)
        assert not any(x.get_active() for x in w.checkboxes.values())
        w.menu_actions['all'].activate(None)
        assert all(x.get_active() for x in w.checkboxes.values() if x.get_sensitive())
        print('PASS: visible footer at 560x420, scrollable content, cancellation, typed values saved, interval units, zero limits persisted, log editor save/reload, About logo and clear menus')
        w.destroy()
    steps=scenario()
    def advance():
        try:next(steps)
        except StopIteration:app.quit();return False
        except Exception:
            import traceback
            errors.append(traceback.format_exc());app.quit();return False
        return True
    GLib.timeout_add(150,advance)
    app.run([])
    if errors:raise SystemExit('\n'.join(errors))
