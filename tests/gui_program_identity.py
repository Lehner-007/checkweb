"""GTK integration: identity errors are localized and never record success."""
import os,sys,tempfile,time,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from modules.gui import App,Window,GLib
from modules.languages import import_pack
from modules.model import DEFAULTS,VERSION,atomic_json,config_dir

with tempfile.TemporaryDirectory(prefix='checkweb-identity-gui-') as tmp:
    os.environ.pop('CHECKWEB_DEV',None)
    os.environ['XDG_CONFIG_HOME']=tmp
    app=App();app.register(None)
    def wait_for(condition):
        until=time.monotonic()+5
        while not condition():
            while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
            if time.monotonic()>until:raise AssertionError('GTK operation timed out')
            time.sleep(.01)
    for code in ('de','en'):
        atomic_json(config_dir()/'settings.json',dict(DEFAULTS,language=code,last_update_check='unchanged'))
        window=Window(app);window.present()
        notices=[]
        window.notify=lambda message,*_:notices.append(message)
        before=(config_dir()/'settings.json').read_bytes()
        for data in ({'program_id':'another-project','version':'999.0.0'},{'version':'999.0.0'}):
            notices.clear()
            with patch('modules.updates.github_json',return_value=data):
                window.check_update('https://raw.githubusercontent.com/example/project/main/version.json')
                wait_for(lambda:not window.update_check_running)
            assert window.update_status_key=='software_check_failed'
            assert not notices
            assert window.opts['last_update_check']=='unchanged'
            assert (config_dir()/'settings.json').read_bytes()==before
        path=Path(tmp)/'foreign.json'
        path.write_text(json.dumps({'program_id':'other','code':'fr','strings':{'start':'Démarrer'},'help_html':'<h1>Aide</h1>'}))
        notices.clear()
        window.background(lambda:import_pack(path),lambda _:notices.append('unexpected success'))
        wait_for(lambda:bool(notices))
        assert notices==[window.tr('wrong_program')]
        assert not (config_dir()/'languages/fr').exists()
        notices.clear()
        with patch('modules.updates.github_json',return_value={'program_id':'checkweb','version':VERSION}):
            window.check_update('https://raw.githubusercontent.com/example/project/main/version.json')
            wait_for(lambda:not window.update_check_running)
        assert window.update_status_key=='software_current'
        assert not notices
        assert window.opts['last_update_check']!='unchanged'
        assert json.loads((config_dir()/'settings.json').read_text())['last_update_check']==window.opts['last_update_check']
        assert window.get_title()==f'checkweb {VERSION}'
        about=window.show_about();assert about.get_version()==VERSION;about.destroy()
        window.destroy()
        print('PASS',code,': localized identity errors, rejected local import, no success state on rejection, valid version saved, GUI version consistent')
