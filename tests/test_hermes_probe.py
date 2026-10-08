"""Launcher regression tests; these do not claim Hermes/macOS acceptance."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv

spec = importlib.util.spec_from_file_location(
    'hermes_probe', Path(__file__).resolve().parents[1] / 'scripts/hermes_import_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class InterpreterSelectionTests(unittest.TestCase):
    def test_symlink_launch_keeps_venv_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            environment = root / 'environment'
            venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
            # A real isolated Python process demonstrates why resolving the launcher is wrong.
            launcher = environment / 'bin/python'
            code = 'import json,sys; print(json.dumps([sys.prefix,sys.base_prefix]))'
            prefix, base = json.loads(subprocess.check_output([str(launcher), '-c', code], text=True))
            self.assertNotEqual(prefix, base)
            prefix, base = json.loads(subprocess.check_output([str(launcher.resolve()), '-c', code], text=True))
            self.assertEqual(prefix, base)

    def test_preserves_launcher_and_validates_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            environment = root / 'environment'
            (environment / 'bin').mkdir(parents=True)
            (environment / 'pyvenv.cfg').write_text('home = managed-python\n')
            target = root / 'managed-python'
            target.write_bytes(b'fixture')
            launcher = environment / 'bin/python'
            launcher.symlink_to(target)
            result = probe.selected_interpreter({'venv': str(environment)}, root)
            self.assertEqual(result, (launcher, environment, target))
            launcher.unlink()
            launcher.symlink_to(Path(sys.executable).resolve())
            with self.assertRaises(ValueError):
                probe.selected_interpreter({'venv': str(environment)}, root)

    def test_missing_venv_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                probe.selected_interpreter({'venv': tmp}, Path(tmp))
