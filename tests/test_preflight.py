from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preflight.py"
SPEC = importlib.util.spec_from_file_location("preflight", MODULE_PATH)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def create_critical_files(self, root: Path) -> None:
        for relative_path in preflight.CRITICAL_FILES:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder", encoding="utf-8")

    def test_critical_files_accepts_untracked_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_critical_files(root)

            def git_runner(*_args, **_kwargs):
                return subprocess.CompletedProcess([], 1, "", "")

            preflight.check_critical_files(root, git_runner)

    def test_critical_files_rejects_tracked_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_critical_files(root)

            def git_runner(*_args, **_kwargs):
                return subprocess.CompletedProcess([], 0, ".env\n", "")

            with self.assertRaisesRegex(preflight.PreflightError, r"\.env is tracked"):
                preflight.check_critical_files(root, git_runner)

    def test_failed_stage_reports_name_and_nonzero_result(self) -> None:
        stderr = StringIO()
        with redirect_stdout(StringIO()), redirect_stderr(stderr):
            succeeded = preflight.run_stage(
                "Secret scan", lambda: (_ for _ in ()).throw(preflight.PreflightError("found secret"))
            )

        self.assertFalse(succeeded)
        self.assertIn("Secret scan: FAILED", stderr.getvalue())
        self.assertIn("Preflight: FAILED", stderr.getvalue())

    @unittest.skipUnless(preflight.sys.platform == "win32", "Windows-specific command resolution")
    def test_frontend_build_uses_npm_cmd_on_windows(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(preflight, "resolve_command", return_value="npm.cmd"), patch.object(
            preflight, "run_command", return_value=completed
        ) as run:
            preflight.check_frontend_build(Path("C:/repo"))

        self.assertEqual(run.call_args.args[0], ["npm.cmd", "run", "build"])

    @unittest.skipUnless(preflight.sys.platform == "win32", "Windows-specific command resolution")
    def test_git_resolves_standard_windows_installation(self) -> None:
        with patch.object(preflight.shutil, "which", return_value=None), patch.object(
            preflight.Path, "is_file", return_value=True
        ):
            self.assertTrue(preflight.resolve_command("git").endswith("Git\\cmd\\git.exe"))


if __name__ == "__main__":
    unittest.main()
