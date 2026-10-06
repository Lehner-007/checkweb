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
        (self.desktop / 'umbenannt.desktop').write_text(lifecycle.MANAGED.replace('Name=Checkweb', 'Name=Mein Checkweb'))
        trash = self.home / '.local/share/Trash'
        (trash / 'files').mkdir(parents=True);(trash / 'info').mkdir()
        (trash / 'files/checkweb.desktop').write_text(lifecycle.DESKTOP)
        (trash / 'info/checkweb.desktop.trashinfo').write_text('Test')
        lifecycle.user_action('remove', self.home)
        self.assertFalse((self.desktop / 'umbenannt.desktop').exists())
        self.assertFalse((trash / 'files/checkweb.desktop').exists())
        self.assertFalse((trash / 'info/checkweb.desktop.trashinfo').exists())

    def test_parent_symlink_does_not_delete_external_data(self):
        external=Path(self.tmp.name)/'unrelated'
        (external/'checkweb').mkdir(parents=True)
        marker=external/'checkweb/keep';marker.write_text('keep')
        shutil=lifecycle.shutil
        shutil.rmtree(self.home/'.config')
        (self.home/'.config').symlink_to(external,target_is_directory=True)
        lifecycle.user_action('remove',self.home)
        self.assertEqual(marker.read_text(),'keep')
        self.assertTrue((self.home/'.config').is_symlink())

    def test_parent_symlink_preserves_foreign_shortcuts(self):
        external=Path(self.tmp.name)/'other-share'
        (external/'applications').mkdir(parents=True)
        target=external/'applications/checkweb.desktop';target.write_text(lifecycle.DESKTOP)
        (self.home/'.local').mkdir()
        (self.home/'.local/share').symlink_to(external,target_is_directory=True)
        lifecycle.user_action('remove',self.home)
        self.assertTrue(target.exists())

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

class CleanupRegressionTests(unittest.TestCase):
    setUp = DesktopLifecycleTests.setUp
    def test_personal_launcher_preserved_and_managed_env_removed(self):
        personal = self.desktop / 'personal.desktop'
        personal.write_text('[Desktop Entry]\nType=Application\nName=Personal\nExec=checkweb --tools\n')
        managed = self.desktop / 'managed-env.desktop'
        managed.write_text(lifecycle.MANAGED.replace('Exec=checkweb', 'Exec=env CHECKWEB_DEV=0 /usr/bin/checkweb --tools'))
        lifecycle.user_action('remove', self.home)
        self.assertTrue(personal.exists())
        self.assertFalse(managed.exists())
        own_named = self.desktop / 'checkweb.desktop'
        own_named.write_text(personal.read_text())
        lifecycle.user_action('configure', self.home)
        self.assertEqual(own_named.read_text(), personal.read_text())

    def test_recorded_custom_xdg_on_real_main_dispatch_without_root_environment(self):
        from modules.runtime_paths import remember_locations
        from types import SimpleNamespace
        custom = self.home / 'individual-config'
        (custom / 'checkweb').mkdir(parents=True)
        (custom / 'checkweb/settings.json').write_text('{}')
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(custom)}):remember_locations(self.home)
        user = SimpleNamespace(pw_name='test-user', pw_uid=1000, pw_shell='/bin/bash', pw_dir=str(self.home))
        def run(command, env, timeout):
            self.assertNotIn('XDG_CONFIG_HOME', env)
            self.assertEqual(command[-2:], ['--user', 'remove'])
            with patch.dict(os.environ, env, clear=True):lifecycle.user_action('remove', self.home)
            return SimpleNamespace(returncode=0)
        with patch.object(lifecycle.os,'geteuid',return_value=0),patch.object(lifecycle.pwd,'getpwall',return_value=[user]),patch.object(lifecycle.subprocess,'run',side_effect=run),patch.object(lifecycle.sys,'argv',['prerm','remove']),patch.dict(os.environ,{'XDG_CONFIG_HOME':'/root/foreign'}):
            lifecycle.main()
        self.assertFalse((custom / 'checkweb').exists())
        self.assertFalse((self.home / '.local/state/checkweb-locations.json').exists())

    def test_optional_runuser_failure_does_not_fail_package_hook(self):
        from types import SimpleNamespace
        import io
        user = SimpleNamespace(pw_name='test-user',pw_uid=1000,pw_shell='/bin/bash',pw_dir=str(self.home))
        for failure in (SimpleNamespace(returncode=1),PermissionError('denied')):
            result = {'side_effect':failure} if isinstance(failure,Exception) else {'return_value':failure}
            stderr=io.StringIO()
            with patch.object(lifecycle.os,'geteuid',return_value=0),patch.object(lifecycle.pwd,'getpwall',return_value=[user]),patch.object(lifecycle.subprocess,'run',**result),patch.object(lifecycle.sys,'argv',['postinst','configure']),patch.object(lifecycle.sys,'stderr',stderr):
                lifecycle.main()
            self.assertIn('nicht vollständig',stderr.getvalue())

    def test_failed_path_does_not_stop_other_paths_and_keeps_registry(self):
        from modules.runtime_paths import remember_locations
        remember_locations(self.home)
        for base in ('.config','.cache'):(self.home/base/'checkweb').mkdir(parents=True,exist_ok=True)
        original = lifecycle.remove_tree
        def remove(path):
            if path == self.home/'.config/checkweb':raise PermissionError('test')
            original(path)
        with patch.object(lifecycle,'remove_tree',side_effect=remove):
            self.assertFalse(lifecycle.user_action('remove',self.home))
        self.assertTrue((self.home/'.config/checkweb').exists())
        self.assertFalse((self.home/'.cache/checkweb').exists())
        self.assertTrue((self.home/'.local/state/checkweb-locations.json').exists())
        lifecycle.user_action('purge',self.home)
        self.assertFalse((self.home/'.local/state/checkweb-locations.json').exists())

    def test_linked_registry_parent_is_not_modified(self):
        external = Path(self.tmp.name) / 'external-state'; external.mkdir()
        registry = external / 'checkweb-locations.json'
        registry.write_text('{"program_id":"checkweb","locations":[]}')
        (self.home/'.local').mkdir(exist_ok=True)
        (self.home/'.local/state').symlink_to(external,target_is_directory=True)
        lifecycle.user_action('purge',self.home)
        self.assertTrue(registry.exists())
