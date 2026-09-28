"""Real GTK smoke test on an available display; no production data."""
import os
import tempfile
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from gi.repository import GLib
from modules.gui import App,Window
from modules.model import config_dir
from modules.reports import save_report

sandbox=tempfile.TemporaryDirectory(prefix='checkweb-gui-')
os.environ['XDG_CONFIG_HOME']=sandbox.name
os.environ.pop('CHECKWEB_DEV',None)
if os.environ.get('CHECKWEB_LANGUAGE_PACK'):
 from modules.languages import import_pack
 from modules.model import atomic_json,DEFAULTS
 code=import_pack(os.environ['CHECKWEB_LANGUAGE_PACK'])
 atomic_json(config_dir()/'settings.json',dict(DEFAULTS,language=code))
if os.environ.get('CHECKWEB_LANGUAGE'):
 from modules.model import atomic_json,DEFAULTS
 atomic_json(config_dir()/'settings.json',dict(DEFAULTS,language=os.environ['CHECKWEB_LANGUAGE']))
if os.environ.get('CHECKWEB_DARK'):
 from gi.repository import Gtk
 Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',True)
root=Path(sandbox.name)/'fixture';root.mkdir()
(root/'index.html').write_text('<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Testseite</title></head><body><h1>Test</h1><img src="fehlt.png"><a href="404.html">Fehler</a><input></body></html>')
app=App();app.register(None)
window=Window(app);window.present()
window.target.set_text(str(root));window.opts['external_links']=False
if os.environ.get('CHECKWEB_UNLIMITED'):
 for key in ('max_pages','max_depth','max_resources','timeout'):window.opts[key]=0
errors=[];stage=0;ticks=0

def check():
 global stage,ticks
 ticks+=1
 try:
  if ticks>150:raise AssertionError('GUI timeout')
  if stage==0:
   window.start_button.emit('clicked');stage=1
  elif stage==1 and window.report:
   assert window.report.status=='complete',window.report.status
   assert any(f.code=='file_missing' for f in window.report.findings)
   assert window.export_button.get_sensitive()
   row=window.listbox.get_row_at_index(0);window.listbox.select_row(row)
   assert window.detail.get_buffer().get_char_count()>0
   save_report(window.report,Path(sandbox.name)/'gui-report.html')
   window.show_settings();stage=2
  elif stage==2:
   from gi.repository import Gtk
   for w in Gtk.Window.get_toplevels():
    if w is not window:w.destroy()
   window.present()
   stage=3
  elif stage==3:
   if os.environ.get('CHECKWEB_SCREENSHOT'):
    subprocess.run(['gnome-screenshot','-w','-f',os.environ['CHECKWEB_SCREENSHOT']],check=True,timeout=10)
   window.set_default_size(800,600);stage=4
  elif stage==4:
   assert window.start_button.get_allocated_width()>0
   window.severity.set_selected(1);window.search.set_text('fehlt')
   window.filter_changed()
   assert window.listbox.get_row_at_index(0) is not None
   window.start_button.emit('clicked');window.cancel_scan();stage=5
  elif stage==5 and window.report:
   assert window.report.status=='cancelled',window.report.status
   print('GTK smoke passed: scan, results, selection, settings, export, resize, filter, cancellation')
   app.quit();return False
 except Exception as exc:
  errors.append(str(exc));app.quit();return False
 return True
GLib.timeout_add(150,check)
app.run([])
sandbox.cleanup()
if errors:raise SystemExit('\n'.join(errors))
