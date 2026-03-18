import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


APP_ROOT = Path(__file__).resolve().parents[1]
MAIN = APP_ROOT / "main.py"

sys.path.insert(0, str(APP_ROOT))
SPEC = importlib.util.spec_from_file_location("py_main_under_test", MAIN)
MAIN_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MAIN_MODULE
SPEC.loader.exec_module(MAIN_MODULE)


def run_app(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        capture_output=True,
        text=True,
        check=False,
        env=base_env,
    )


def write_fake_python(path: Path, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'Python {version}\\n'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


class MainContractTests(unittest.TestCase):
    def test_no_args_matches_dash_h(self) -> None:
        no_args = run_app()
        help_args = run_app("-h")
        self.assertEqual(no_args.returncode, 0)
        self.assertEqual(no_args.stdout, help_args.stdout)

    def test_version_is_single_line(self) -> None:
        result = run_app("-v")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "0.0.0")

    def test_help_has_no_ansi_styling(self) -> None:
        result = run_app("-h")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("\x1b", result.stdout)

    def test_upgrade_invokes_install_script_with_dash_u(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "marker.txt"
            install_script = Path(temp_dir) / "install.sh"
            install_script.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" > \"$PY_MARKER\"\n",
                encoding="utf-8",
            )
            install_script.chmod(0o755)

            result = run_app(
                "-u",
                env={
                    "PY_INSTALL_SCRIPT": str(install_script),
                    "PY_MARKER": str(marker),
                },
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8").strip(), "-u")

    def test_frozen_install_script_path_uses_executable_directory(self) -> None:
        with mock.patch.object(MAIN_MODULE.sys, "frozen", True, create=True):
            with mock.patch.object(MAIN_MODULE.sys, "executable", "/tmp/py/py"):
                self.assertEqual(
                    MAIN_MODULE.app_install_script_path(),
                    Path("/tmp/py/install.sh"),
                )

    def test_minor_selector_emits_shell_script_and_scrubs_stale_python_bin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            path_312 = home_dir / ".local" / "share" / "mise" / "installs" / "python" / "3.12.13" / "bin" / "python"
            path_314 = home_dir / ".local" / "share" / "mise" / "installs" / "python" / "3.14.3" / "bin" / "python"
            write_fake_python(path_312, "3.12.13")
            write_fake_python(path_314, "3.14.3")

            env = {
                "HOME": str(home_dir),
                "PATH": f"{path_314.parent}:{os.environ['PATH']}",
            }
            result = run_app("312", env=env)

            self.assertEqual(result.returncode, 0)
            self.assertIn(str(path_312.parent), result.stdout)
            self.assertNotIn(f"{path_314.parent}:", result.stdout)
            self.assertIn("Using Python 3.12.13", result.stdout)

    def test_system_selector_emits_usr_bin_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            path_314 = home_dir / ".local" / "share" / "mise" / "installs" / "python" / "3.14.3" / "bin" / "python"
            write_fake_python(path_314, "3.14.3")

            env = {
                "HOME": str(home_dir),
                "PATH": f"{path_314.parent}:{os.environ['PATH']}",
            }
            result = run_app("s", env=env)

            self.assertEqual(result.returncode, 0)
            self.assertIn("export PATH=/usr/bin", result.stdout)
            self.assertNotIn(str(path_314.parent), result.stdout)

    def test_ls_shows_installed_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            path_312 = home_dir / ".local" / "share" / "mise" / "installs" / "python" / "3.12.13" / "bin" / "python"
            path_314 = home_dir / ".local" / "share" / "mise" / "installs" / "python" / "3.14.3" / "bin" / "python"
            write_fake_python(path_312, "3.12.13")
            write_fake_python(path_314, "3.14.3")

            result = run_app("ls", env={"HOME": str(home_dir)})

            self.assertEqual(result.returncode, 0)
            self.assertIn("312", result.stdout)
            self.assertIn("314", result.stdout)

    def test_missing_runtime_shows_install_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_app("312", env={"HOME": temp_dir})
            self.assertEqual(result.returncode, 1)
            self.assertIn("mise install python@3.12", result.stderr)


if __name__ == "__main__":
    unittest.main()
