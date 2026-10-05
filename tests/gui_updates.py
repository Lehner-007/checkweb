"""Real GTK update status, fixed sources, four lines and tools dialog."""
import os,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from modules.gui import App,Window,Gtk,GLib
from modules.model import VERSION
from modules.menus import descendants,compact_menus
from gi.repository import Gio

def pump(seconds=.15):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
  time.sleep(.01)
def wait(condition):
 end=time.monotonic()+8
 while not condition():
  pump(.03)
  assert time.monotonic()<end,'GUI timeout'
with tempfile.TemporaryDirectory() as tmp:
 os.environ['XDG_CONFIG_HOME']=tmp
 app=App();app.register(None)
 with patch.object(Window,'initial_update',lambda *_:False):
  w=Window(app);w.present();pump()
  d=w.show_settings();pump();c=d.template_controls
  assert 'update_url' not in c['fields'] and 'source_url' not in c['fields']
  for code in ('de','en'):
   w.apply_language(code)
   for version,status,active in ((VERSION,'software_current',False),('9.0.0','software_update',True)):
    with patch('modules.gui.release_info',return_value={'version':version,'deb':{'url':'test'}}):
     w.check_update();wait(lambda:not w.update_check_running)
    assert c['update_status'].get_label()==w.tr(status)
    assert c['download'].get_sensitive()==active
   with patch('modules.gui.release_info',side_effect=ValueError('invalid')):
    w.check_update();wait(lambda:not w.update_check_running)
   assert c['update_status'].get_label()==w.tr('software_check_failed') and not c['download'].get_sensitive()
  d.destroy();assert not w.settings_windows
  about=w.show_about();pump();logo=about.get_logo()
  assert logo.get_width()<=128 and logo.get_height()<=128
  about.destroy()
  w.show_progress();pump();window=w.progress_window
  sizes=[]
  for text in ('short','one\ntwo\nthree\nfour','https://example.org/'+'longtext'*150):
   w.progress_label.set_label(text);pump();sizes.append((window.get_width(),window.get_height()))
  assert len(set(sizes))==1,sizes
  w.close_progress()
  info=w.show_tools();wait(lambda:info.tool_results is not None)
  assert info.tool_results and any(item['name']=='html5lib' for item in info.tool_results)
  assert not any(item['name']=='tidy' for item in info.tool_results)
  info.close();pump()
  menu=Gio.Menu();submenu=Gio.Menu();submenu.append('One','win.settings');menu.append_submenu('Only',submenu)
  bar=Gtk.PopoverMenuBar.new_from_model(menu);w.get_child().append(bar);compact_menus(bar);pump()
  scroll=next(x for x in descendants(bar) if isinstance(x,Gtk.ScrolledWindow))
  assert scroll.get_policy()[1]==Gtk.PolicyType.NEVER
  w.close();pump()
 print('PASS: DE/EN status, download gating, rejected metadata, hidden sources, settings cleanup, 128px logo, stable four-line progress, actual tools and compact single-item menu')
