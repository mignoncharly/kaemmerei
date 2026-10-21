"""Native manager safety checks; no installed cluster or Windows service touched."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import native_test_database as native
from tests.support import scratch_directory


class NativeManagerTests(unittest.TestCase):
    def test_pg_ctl_start_uses_regular_file_instead_of_inherited_pipes(self):
        with scratch_directory('ohvr-start-log-') as directory:
            with patch.object(native.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
                native.run_pg_ctl_start(['pg_ctl', 'start'], output_log=Path(directory) / 'start.log')
                options = run.call_args.kwargs
                self.assertNotIn('capture_output', options)
                self.assertNotEqual(options['stdout'], native.subprocess.PIPE)
                self.assertEqual(options['stderr'], native.subprocess.STDOUT)
                self.assertEqual(options['stdin'], native.subprocess.DEVNULL)
                self.assertEqual(options['timeout'], 45)

    def test_binary_cluster_identity_rejects_mismatch_and_truncation(self):
        from unittest.mock import MagicMock
        self.cluster.prepare_home()
        control = self.cluster.data / 'global' / 'pg_control'
        control.parent.mkdir(parents=True)
        control.write_bytes(b'12345678')
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = (memoryview(b'12345678'),)
        self.cluster.assert_connected_cluster(connection)
        self.assertIn('pg_read_binary_file', connection.execute.call_args.args[0])
        connection.execute.return_value.fetchone.return_value = (b'87654321',)
        with self.assertRaisesRegex(native.SetupError, 'identity'):
            self.cluster.assert_connected_cluster(connection)
        control.write_bytes(b'123')
        with self.assertRaisesRegex(native.SetupError, 'incomplete'):
            self.cluster.assert_connected_cluster(connection)

    def test_existing_setup_lock_is_never_removed(self):
        self.cluster.prepare_home()
        lock = self.cluster.home / '.setup.lock'
        lock.write_text(str(os.getpid()))
        with self.assertRaises(native.SetupError):
            with native.setup_lock(self.cluster.home):
                self.fail('Active lock was ignored')
        self.assertEqual(lock.read_text(), str(os.getpid()))

    def setUp(self):
        self.stack = self.enterContext(ExitStack())
        self.root = Path(self.enterContext(scratch_directory("ohvr-native-unit-")))
        self.binaries = self.root / "bin"
        self.binaries.mkdir()
        for name in ("initdb", "pg_ctl"):
            (self.binaries / (name + (".exe" if os.name == "nt" else ""))).touch()
        self.cluster = native.NativeCluster(self.root / "cluster", self.binaries)
        # Unit fixtures use synthetic secrets and inherited workspace ACLs. Real
        # platform directory protection is exercised by the native CI smoke job.
        self.stack.enter_context(patch.object(native, "secure_directory"))

    def test_business_and_project_roots_are_rejected(self):
        for path in (native.ROOT, native.ROOT / "data", native.ROOT / "app", native.ROOT.parent / "outside"):
            with self.subTest(path=path), self.assertRaises(native.SetupError):
                native.checked_home(path)

    def test_unmarked_existing_directory_is_never_adopted(self):
        self.cluster.home.mkdir()
        sentinel = self.cluster.home / "do-not-touch.txt"
        sentinel.write_text("synthetic existing content")
        with self.assertRaisesRegex(native.SetupError, "unmarked"):
            self.cluster.prepare_home()
        self.assertEqual(sentinel.read_text(), "synthetic existing content")
        self.assertFalse(self.cluster.marker.exists())

    def test_marker_port_mismatch_is_rejected(self):
        self.cluster.prepare_home()
        other = native.NativeCluster(self.cluster.home, self.binaries, 55433)
        with self.assertRaisesRegex(native.SetupError, "does not match"):
            other.metadata()

    def test_passfile_reuse_and_connection_metadata_do_not_expose_password(self):
        self.cluster.prepare_home()
        password = self.cluster.secret(native.TEST_USER)
        self.assertEqual(self.cluster.secret(native.TEST_USER), password)
        self.assertNotIn(password, json.dumps(self.cluster.connection_info()))
        self.assertNotIn("password", self.cluster.connection_info()["url"])
        self.assertEqual(self.cluster.passfile(native.TEST_USER).read_text().strip(),
                         f"127.0.0.1:55432:*:ohvr_verify:{password}")
        if os.name != "nt":
            self.assertEqual(self.cluster.passfile(native.TEST_USER).stat().st_mode & 0o777, 0o600)

    def test_failed_init_retains_marker_but_removes_password_input(self):
        self.cluster.prepare_home()
        with patch.object(native, "run_command", side_effect=native.SetupError("synthetic init failure")):
            with self.assertRaises(native.SetupError):
                self.cluster.initialize()
        self.assertFalse((self.cluster.home / "init-password.input").exists())
        self.assertTrue(self.cluster.marker.exists())
        self.assertTrue(self.cluster.passfile(native.BOOTSTRAP).exists())

    def test_incomplete_data_is_preserved(self):
        self.cluster.prepare_home()
        self.cluster.data.mkdir()
        sentinel = self.cluster.data / "incomplete-file"
        sentinel.write_text("synthetic incomplete initialization")
        with self.assertRaisesRegex(native.SetupError, "Incomplete"):
            self.cluster.initialize()
        self.assertTrue(sentinel.exists())

    def test_live_cluster_is_not_reconfigured_or_restarted(self):
        self.cluster.prepare_home()
        with patch.object(self.cluster, "initialize"), patch.object(self.cluster, "status", return_value="running"), \
                patch.object(self.cluster, "configure") as configure, \
                patch.object(self.cluster, "provision_role") as provision, \
                patch.object(native, "run_command") as command:
            result = self.cluster.start()
        configure.assert_not_called()
        command.assert_not_called()
        provision.assert_called_once()
        self.assertEqual(result["port"], 55432)

    def test_stop_is_confined_to_marked_data_and_retains_storage(self):
        self.cluster.prepare_home()
        with patch.object(self.cluster, "status", return_value="running"), \
                patch.object(native, "run_command") as command:
            result = self.cluster.stop()
        self.assertIn(self.cluster.data, command.call_args.args[0])
        self.assertIn("stop", command.call_args.args[0])
        self.assertTrue(result["data_preserved"])
        self.assertTrue(self.cluster.home.exists())

    def test_token_failure_is_actionable_without_security_bypass(self):
        result = SimpleNamespace(returncode=1, stderr="could not create restricted token: error code 87", stdout="")
        with patch.object(native.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(native.SetupError, "normal authorized PowerShell"):
                native.run_command([self.cluster.executable("initdb"), "--version"])

    def test_major_version_mismatch_is_rejected(self):
        self.cluster.prepare_home()
        self.cluster.data.mkdir()
        (self.cluster.data / "PG_VERSION").write_text("18")
        with patch.object(native, "run_command", return_value=SimpleNamespace(stdout="initdb (PostgreSQL) 17.7")):
            with self.assertRaisesRegex(native.SetupError, "different major versions"):
                self.cluster.initialize()


if __name__ == "__main__":
    unittest.main(verbosity=2)
