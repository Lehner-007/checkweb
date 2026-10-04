#!/usr/bin/python3
"""Manage Checkweb desktop entries and private runtime data, as their owner."""
import os
import configparser
import shlex
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

DESKTOP = '''[Desktop Entry]
Type=Application
Name=Checkweb
GenericName=Website checker
GenericName[de]=Webseitenprüfung
Comment=Check local and online websites
Comment[de]=Lokale und Online-Webseiten prüfen
Exec=checkweb
Icon=/usr/share/checkweb/assets/checkweb.png
Terminal=false
Categories=Development;WebDevelopment;
Keywords=HTML;CSS;Web;Website;
StartupNotify=true
'''
MANAGED = DESKTOP + 'X-Checkweb-Managed=true\n'


def desktop_dir(home):
    config = home / '.config/user-dirs.dirs'
    try:
        for line in config.read_text().splitlines():
            if line.startswith('XDG_DESKTOP_DIR='):
                value = line.split('=', 1)[1].strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                    if value == '$HOME':
                        return None  # Disabled desktop directory.
                    value = value.replace('${HOME}', str(home)).replace('$HOME', str(home))
                    target = Path(value)
                    if target.is_absolute() and target != home and target.is_dir():
                        return target
    except FileNotFoundError:
        pass
    return next((home / n for n in ('Schreibtisch', 'Desktop') if (home / n).is_dir()), None)


def is_shortcut(path):
    if path.is_symlink():
        return os.readlink(path) == '/usr/share/applications/checkweb.desktop'
    if not path.is_file():
        return False
    try:
        cfg = configparser.ConfigParser(interpolation=None, strict=False)
        cfg.read_string(path.read_text())
        command = shlex.split(cfg.get('Desktop Entry', 'Exec', fallback=''))
        return bool(command) and command[0] in ('checkweb', '/usr/bin/checkweb')
    except (OSError, UnicodeError, ValueError, configparser.Error):
        return False


def safe_parents(path,include_self=False):
    path=Path(os.path.abspath(path))
    candidates=[path,*path.parents] if include_self else path.parents
    if any(parent.is_symlink() for parent in candidates):
        print('Checkweb: verlinkter Speicherort bleibt erhalten:',path,file=sys.stderr)
        return False
    return True


def remove_tree(path):
    # Never follow a directory symlink into unrelated user files.
    if not safe_parents(path):
        return
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def user_action(action, home):
    desktop = desktop_dir(home)
    if action == 'configure':
        if desktop is None:
            return
        target = desktop / 'checkweb.desktop'
        if (target.exists() or target.is_symlink()) and not is_shortcut(target):
            print('Checkweb: eigene Desktop-Datei bleibt erhalten:', target, file=sys.stderr)
            return
        if target.is_symlink():
            target.unlink()
        # Run as user, never as root; no privilege escalation via user paths.
        target.write_text(MANAGED)
        target.chmod(0o755)
        if shutil.which('gio'):
            subprocess.run(['gio', 'set', str(target), 'metadata::trusted', 'true'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return
    if action not in ('remove', 'purge'):
        return
    for folder in filter(None, [desktop, home / '.local/share/applications', home / '.config/autostart']):
        if safe_parents(folder,include_self=True) and folder.is_dir():
            for target in folder.glob('*.desktop'):
                if is_shortcut(target):
                    target.unlink()
    trash = home / '.local/share/Trash'
    if safe_parents(trash / 'files',include_self=True) and (trash / 'files').is_dir():
        for target in (trash / 'files').glob('*.desktop'):
            if is_shortcut(target):
                target.unlink()
                info=trash / 'info' / (target.name + '.trashinfo')
                if safe_parents(info):info.unlink(missing_ok=True)
    # App-owned XDG directories only; never the development project or arbitrary reports.
    locations = [home / '.config', home / '.cache', home / '.local/share', home / '.local/state']
    for var in ('XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME'):
        value = os.environ.get(var)
        if value and Path(value).is_absolute():
            locations.append(Path(value))
    for base in set(locations):
        remove_tree(base / 'checkweb')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--user':
        if os.geteuid() == 0:
            raise SystemExit('Benutzerbereinigung darf nicht als root laufen.')
        user_action(sys.argv[2], Path(pwd.getpwuid(os.geteuid()).pw_dir))
        return
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    if action not in ('configure', 'remove', 'purge'):
        return  # No deletion on upgrade, failed upgrade, or deconfigure.
    if os.geteuid() != 0:
        raise SystemExit('Paketverwaltung benötigt root.')
    failed = []
    for user in pwd.getpwall():
        if not 1000 <= user.pw_uid < 65534 or user.pw_shell.endswith(('/nologin', '/false')):
            continue
        if not Path(user.pw_dir).is_dir():
            print('Checkweb: Benutzerordner nicht erreichbar:',user.pw_name,file=sys.stderr)
            continue
        # Root-XDG-Pfade gehören nicht zum Zielbenutzer.
        environment=os.environ.copy()
        for key in ('XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','XDG_STATE_HOME'):
            environment.pop(key,None)
        result = subprocess.run(['/usr/sbin/runuser', '-u', user.pw_name, '--',
                                 '/usr/bin/python3', '-B', str(Path(__file__).resolve()), '--user', action],env=environment)
        if result.returncode:
            failed.append(user.pw_name)
    if failed:
        raise SystemExit('Checkweb-Benutzerdateien nicht vollständig bearbeitet: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
