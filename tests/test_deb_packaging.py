"""DEB desktop lifecycle without touching the real user's directories."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('desktop_lifecycle', Path(__file__).resolve().parents[1] / 'packaging/desktop_lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class DesktopLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.desktop = self.home / 'Mein Desktop'
        self.desktop.mkdir(parents=True)
        (self.home / '.config').mkdir()
        (self.home / '.config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Mein Desktop"\n')
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.which = patch.object(lifecycle.shutil, 'which', return_value=None)
        self.which.start()
        self.addCleanup(self.which.stop)

    def test_install_repeat_upgrade_remove_all_app_data(self):
        lifecycle.user_action('configure', self.home)
        target = self.desktop / 'checkweb.desktop'
        self.assertTrue(target.exists())
        self.assertTrue(target.stat().st_mode & 0o100)
        for base in ['.config', '.cache', '.local/share', '.local/state']:
            folder = self.home / base / 'checkweb'
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'eigene-sprache.json').write_text('{"test":true}')
        lifecycle.user_action('configure', self.home)
        lifecycle.user_action('upgrade', self.home)
        self.assertTrue((self.home / '.config/checkweb/eigene-sprache.json').exists())
        unrelated = self.desktop / 'mein-bericht.html'
        unrelated.write_text('Benutzerdokument')
        lifecycle.user_action('remove', self.home)
        self.assertFalse(target.exists())
        for base in ['.config', '.cache', '.local/share', '.local/state']:
            self.assertFalse((self.home / base / 'checkweb').exists())
        self.assertTrue(unrelated.exists())
        lifecycle.user_action('remove', self.home)

    def test_symlink_does_not_delete_external_data(self):
        external = Path(self.tmp.name) / 'unrelated'
        external.mkdir();(external / 'wichtig').write_text('behalten')
        (self.home / '.config/checkweb').symlink_to(external, target_is_directory=True)
        lifecycle.user_action('remove', self.home)
        self.assertTrue((external / 'wichtig').exists())
        self.assertFalse((self.home / '.config/checkweb').is_symlink())

    def test_old_shortcut_trash_and_renamed_shortcut_removed(self):
        (self.desktop / 'umbenannt.desktop').write_text(lifecycle.DESKTOP.replace('Name=Checkweb', 'Name=Mein Checkweb'))
        trash = self.home / '.local/share/Trash'
        (trash / 'files').mkdir(parents=True);(trash / 'info').mkdir()
        (trash / 'files/checkweb.desktop').write_text(lifecycle.DESKTOP)
        (trash / 'info/checkweb.desktop.trashinfo').write_text('Test')
        lifecycle.user_action('remove', self.home)
        self.assertFalse((self.desktop / 'umbenannt.desktop').exists())
        self.assertFalse((trash / 'files/checkweb.desktop').exists())
        self.assertFalse((trash / 'info/checkweb.desktop.trashinfo').exists())

    def test_unrelated_shortcut_not_overwritten(self):
        target = self.desktop / 'checkweb.desktop'
        target.write_text('[Desktop Entry]\nExec=other-app\n')
        lifecycle.user_action('configure', self.home)
        lifecycle.user_action('remove', self.home)
        self.assertIn('other-app', target.read_text())

    def test_disabled_desktop_and_custom_xdg(self):
        (self.home / '.config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME"\n')
        lifecycle.user_action('configure', self.home)
        self.assertFalse((self.desktop / 'checkweb.desktop').exists())
        custom = self.home / 'custom-config'
        (custom / 'checkweb').mkdir(parents=True)
        (custom / 'checkweb/settings.json').write_text('{}')
        with patch.dict(os.environ, {'XDG_CONFIG_HOME':str(custom)}):
            lifecycle.user_action('remove', self.home)
        self.assertFalse((custom / 'checkweb').exists())


if __name__ == '__main__':
    unittest.main()
