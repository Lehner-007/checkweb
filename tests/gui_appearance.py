"""Echte GTK-Darstellung mit isolierten Daten, ohne Systemänderungen."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from modules.gui import App,Window,Gtk,GLib
from modules.model import Report,Finding


def widgets(widget):
    yield widget
    child=widget.get_first_child()
    while child:
        yield from widgets(child)
        child=child.get_next_sibling()


def pump(seconds=.3):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(.005)


with tempfile.TemporaryDirectory(prefix='checkweb-appearance-') as temporary:
    os.environ.pop('CHECKWEB_DEV',None)
    os.environ['XDG_CONFIG_HOME']=temporary
    os.environ['GSETTINGS_BACKEND']='memory'
    app=App();app.register(None)
    window=Window(app);window.present();pump()
    try:
        for dark in (False,True):
            Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',dark)
            for code in ('de','en'):
                window.apply_language(code);pump()
                model=window.menu_bar.get_menu_model().get_item_link(0,'submenu')
                assert model.get_n_items()==3
                assert model.get_item_link(1,'section').get_item_attribute_value(0,'action',None).get_string()=='win.settings'
                assert model.get_item_link(2,'section').get_item_attribute_value(0,'action',None).get_string()=='win.quit'
                popover=next(w for w in widgets(window.menu_bar.get_first_child()) if isinstance(w,Gtk.PopoverMenu))
                popover.popup();pump()
                separators=[w for w in widgets(popover) if isinstance(w,Gtk.Separator)]
                assert len(separators)==2
                assert all(w.get_mapped() and w.get_height()>=1 and w.get_width()>20 for w in separators)
                popover.popdown();pump()
                dialog=window.show_settings();pump()
                body=dialog.get_child().get_first_child().get_child()
                contents=list(widgets(body))
                heading=next(w for w in contents if isinstance(w,Gtk.Label) and w.get_label()==window.tr('language_extensions'))
                language=next(w for w in contents if w.get_name()=='installed_languages')
                source=next(w for w in contents if isinstance(w,Gtk.Label) and w.get_label()==window.tr('source_url'))
                assert contents.index(heading)<contents.index(language)<contents.index(source)
                dialog.destroy()
            window.report=Report('local',temporary,[],status='complete',findings=[
                Finding('error','links','a.html','file_missing'),
                Finding('warning','images','b.html','image_alt')])
            window.render();window.listbox.unselect_all();pump()
            from PIL import Image
            view=window.listbox
            snapshot=Gtk.Snapshot()
            Gtk.WidgetPaintable.new(view).snapshot(snapshot,view.get_width(),view.get_height())
            texture=window.get_renderer().render_texture(snapshot.to_node(),None)
            imagefile=Path(temporary)/'rows.png';texture.save_to_png(str(imagefile))
            with Image.open(imagefile) as image:
                colors=[image.getpixel((2,int(row.get_allocation().y+row.get_height()/2)))
                        for row in (view.get_row_at_index(0),view.get_row_at_index(1))]
            assert colors[0]!=colors[1],(dark,colors)
        # Nur das Fortschrittsfenster hat den Balken; Hauptfenster ohne Aktionsleiste.
        assert not any(isinstance(w,Gtk.ProgressBar) for w in widgets(window))
        forbidden={window.tr(key) for key in ('start','cancel','export')}
        assert not any(isinstance(w,Gtk.Button) and w.get_label() in forbidden for w in widgets(window))
        window.set_running(True);pump(.6)
        progress=window.progress_window
        assert progress.get_mapped() and progress.get_modal() and progress.get_transient_for() is window
        window.update_progress(7,'Aktuelle Datei')
        assert 'Aktuelle Datei' in window.progress_label.get_label()
        if shutil.which('xwininfo'):
            import gi
            gi.require_version('GdkX11','4.0')
            from gi.repository import GdkX11
            if isinstance(window.get_surface(),GdkX11.X11Surface):
                def geometry(widget):
                    xid=GdkX11.X11Surface.get_xid(widget.get_surface())
                    text=subprocess.check_output(['xwininfo','-id',str(xid)],text=True)
                    return [int(re.search(key+r':\s*(-?\d+)',text).group(1)) for key in
                            ('Absolute upper-left X','Absolute upper-left Y','Width','Height')]
                parent,child=geometry(window),geometry(progress)
                assert all(abs(parent[i]+parent[i+2]/2-child[i]-child[i+2]/2)<=3 for i in (0,1)),(parent,child)
        progress.close();pump()
        assert window.cancel_event.is_set() and not window.progress_cancel.get_sensitive()
        assert progress.get_visible(), 'Abbruch wartet auf das tatsächliche Ende'
        window.scan_done(window.report);pump()
        assert window.progress_window is None and not progress.get_visible()
        window.set_running(True)
        window.notify=lambda *_:None
        window.worker_error('isolierter Testfehler');pump()
        assert window.progress_window is None
        print('PASS: sichtbare Menütrenner und Sprachordnung DE/EN Hell/Dunkel, gemalte Zeilenfarben, Fortschrittszentrierung, Abbruch wartet, Abschluss und Fehler schließen das Fenster')
    finally:
        window.close_progress();window.destroy()
