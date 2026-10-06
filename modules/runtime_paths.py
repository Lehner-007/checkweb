"""Remember actual user XDG locations for later package cleanup, without profiles."""
import json
import logging
import os
from pathlib import Path
from .model import atomic_json

VARIABLES = {'XDG_CONFIG_HOME': '.config', 'XDG_CACHE_HOME': '.cache',
             'XDG_DATA_HOME': '.local/share', 'XDG_STATE_HOME': '.local/state'}


def remember_locations(home=None):
    home = Path(home) if home is not None else Path.home()
    registry = home / '.local/state/checkweb-locations.json'
    if any(parent.is_symlink() for parent in (registry, *registry.parents)):
        raise OSError('Linked cleanup registry is not used')
    locations = set()
    if registry.exists():
        data = json.loads(registry.read_text())
        if not isinstance(data, dict) or data.get('program_id') != 'checkweb' or not isinstance(data.get('locations'), list):
            raise ValueError('Invalid cleanup registry')
        locations.update(value for value in data['locations'] if isinstance(value, str)
                         and Path(value).is_absolute() and Path(value).name == 'checkweb')
    for variable, default in VARIABLES.items():
        value = os.environ.get(variable, '')
        base = Path(value) if value and Path(value).is_absolute() else home / default
        locations.add(str(base / 'checkweb'))
    atomic_json(registry, {'program_id': 'checkweb', 'locations': sorted(locations)})


def remember_installed_locations():
    from .model import ROOT
    if ROOT != Path('/usr/share/checkweb'):
        return  # Private development copies are not installation leftovers.
    if os.geteuid() == 0:
        logging.warning('Checkweb läuft als root; Benutzerbereinigung erfasst dieses Konto nicht.')
        return
    try:
        remember_locations()
    except (OSError, ValueError):
        logging.warning('Checkweb-Speicherorte konnten nicht vorgemerkt werden.', exc_info=True)
