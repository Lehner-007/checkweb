"""Isolated real-GTK language choices; network is mocked, no user data changed."""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.model import ROOT
from modules.gui import App,Window
from gi.repository import Gtk,GLib

def walk(w):
    yield w
    child=w.get_first_child()
    while child:
        yield from walk(child)
        child=child.get_next_sibling()

def named(w,name):return next(x for x in walk(w) if x.get_name()==name)
def labels(drop):return [drop.get_model().get_string(i) for i in range(drop.get_model().get_n_items())]

def close_dialogs(window,settings=None):
    for w in list(Gtk.Window.get_toplevels()):
        if w not in (window,settings):w.destroy()

with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp,'CHECKWEB_DEV':'0'}):
    app=App();app.register(None)
    window=Window(app);window.present()
    window.background=lambda fn,done,quiet=False:done(fn())
    settings=window.show_settings()
    installed=named(settings,'installed_languages')
    assert labels(installed)==['Deutsch','Englisch'],labels(installed)
    catalog=json.loads((ROOT/'github/sprachpakete/catalog.json').read_text())
    def fetch(url):
        name=url.rsplit('/',1)[-1]
        return json.loads((ROOT/'github/sprachpakete'/name).read_text())
    # Use the exact callback installed by the real settings button.
    download_button=next(x for x in walk(settings) if isinstance(x,Gtk.Button) and x.get_label()==window.tr('download_language'))
    with patch('modules.languages.github_json',side_effect=fetch):
        download_button.emit('clicked')
        dialog=next(w for w in Gtk.Window.get_toplevels() if isinstance(w,Gtk.Dialog) and w.get_title()==window.tr('download_language'))
        choice=named(dialog,'download_languages')
        names=labels(choice);assert len(names)==8,names
        assert 'Französisch' in names and 'fr' not in names
        choice.set_selected(names.index('Französisch'))
        dialog.response(Gtk.ResponseType.OK)
        assert 'Französisch' in labels(installed),labels(installed)
        assert installed.get_selected_item().get_string()=='Französisch'
    close_dialogs(window,settings)
    with patch('modules.languages.github_json',return_value=catalog):
        dialog=window.download_language(window.opts['source_url'],parent=settings)
        assert 'Französisch' not in labels(named(dialog,'download_languages'))
        dialog.response(Gtk.ResponseType.CANCEL)
    with patch('modules.languages.github_json',side_effect=OSError('offline')):
        dialog=window.download_language(window.opts['source_url'],parent=settings)
        assert not dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive()
        assert any(isinstance(x,Gtk.Label) and 'offline' in x.get_text() for x in walk(dialog))
        dialog.response(Gtk.ResponseType.CANCEL)
    settings.destroy()
    from modules.i18n import Strings
    window.tr=Strings('en')
    settings=window.show_settings()
    assert labels(named(settings,'installed_languages'))==['German','English','French']
    settings.set_default_size(480,400)
    settings.destroy();window.destroy()
    print('GTK-Sprachauswahl: Namen, acht Downloads, Installation, sofortige Aktualisierung und Offline-Fehler geprüft.')
