#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Iterable

from _version import __version__


APP_NAME = "py"
APP_ROOT = Path(__file__).resolve().parent
ANSI_GRAY = "\033[38;5;245m"
ANSI_RESET = "\033[0m"
SYSTEM_SELECTOR = "s"

HELP_TEXT = """py
shell-first Python selector over system Python and installed mise runtimes

flags:
  py -h
    show this help
  py -v
    print the installed version
  py -u
    upgrade to the latest release

features:
  switch the current shell to system Python or an installed Python minor
  # py s | py 312 | py 314
  py s
  py 312
  py 314

  inspect installed selectors and the currently active python
  # py ls | py which
  py ls
  py which
"""


class UsageError(RuntimeError):
    pass


@dataclass(frozen=True)
class Runtime:
    version: str
    bin_dir: Path
    python_path: Path

    @property
    def selector(self) -> str:
        major, minor, _ = parse_version(self.version)
        return f"{major}{minor:02d}"

    @property
    def minor(self) -> str:
        major, minor, _ = parse_version(self.version)
        return f"{major}.{minor}"


def muted(text: str) -> str:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{ANSI_GRAY}{text}{ANSI_RESET}"


def print_help() -> None:
    print(muted(HELP_TEXT.rstrip()))


def home_dir() -> Path:
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def mise_python_root() -> Path:
    return home_dir() / ".local" / "share" / "mise" / "installs" / "python"


def install_script_path() -> Path:
    override = os.environ.get("PY_INSTALL_SCRIPT")
    return Path(override) if override else APP_ROOT / "install.sh"


def parse_version(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise ValueError(f"invalid version: {value}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def read_python_version(python_path: str | Path) -> str:
    result = subprocess.run(
        [str(python_path), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (result.stdout or result.stderr).strip()
    return text or "Python unavailable"


def installed_runtimes() -> list[Runtime]:
    root = mise_python_root()
    runtimes: list[Runtime] = []
    if not root.exists():
        return runtimes

    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            parse_version(child.name)
        except ValueError:
            continue
        python_path = child / "bin" / "python"
        if not python_path.exists():
            continue
        runtimes.append(Runtime(version=child.name, bin_dir=python_path.parent, python_path=python_path))

    return sorted(runtimes, key=lambda item: parse_version(item.version))


def latest_runtimes_by_minor() -> list[Runtime]:
    latest: dict[str, Runtime] = {}
    for runtime in installed_runtimes():
        latest[runtime.minor] = runtime
    return sorted(latest.values(), key=lambda item: parse_version(item.version))


def current_python_path() -> str | None:
    return shutil.which("python")


def current_python_version() -> str:
    path = current_python_path()
    if path is None:
        return "python not found"
    return read_python_version(path)


def active_selector() -> str | None:
    path = current_python_path()
    version_text = current_python_version()
    version_value = version_text.split(" ", 1)[1] if version_text.startswith("Python ") else ""

    if path == "/usr/bin/python":
        return SYSTEM_SELECTOR

    for runtime in latest_runtimes_by_minor():
        if path == str(runtime.python_path):
            return runtime.selector
        if version_value == runtime.version:
            return runtime.selector

    if path and not path.startswith(str(mise_python_root())) and "/shims/" not in path:
        return SYSTEM_SELECTOR
    return None


def normalize_selector(token: str) -> str:
    raw = token.strip().lower()
    if raw in {SYSTEM_SELECTOR, "sys", "system"}:
        return SYSTEM_SELECTOR
    if raw.count(".") == 2:
        parse_version(raw)
        return raw
    if raw.count(".") == 1:
        major, minor = raw.split(".", 1)
        if not (major.isdigit() and minor.isdigit()):
            raise UsageError("usage: py s | py 312 | py 314 | py ls | py which")
        return f"{int(major)}.{int(minor)}"
    if raw.isdigit() and len(raw) >= 3:
        return f"{int(raw[0])}.{int(raw[1:])}"
    raise UsageError("usage: py s | py 312 | py 314 | py ls | py which")


def resolve_runtime(token: str) -> Runtime:
    normalized = normalize_selector(token)
    runtimes = installed_runtimes()

    if normalized == SYSTEM_SELECTOR:
        raise UsageError("system python does not resolve to a mise runtime")

    if normalized.count(".") == 2:
        for runtime in runtimes:
            if runtime.version == normalized:
                return runtime
        raise UsageError(
            f"python {normalized} is not installed via mise.\n"
            f"Install it with: mise install python@{normalized}"
        )

    matches = [runtime for runtime in runtimes if runtime.version.startswith(f"{normalized}.")]
    if matches:
        return matches[-1]
    raise UsageError(
        f"python {normalized} is not installed via mise.\n"
        f"Install it with: mise install python@{normalized}"
    )


def strip_python_install_bins(path_value: str) -> list[str]:
    root_prefix = str(mise_python_root()) + os.sep
    cleaned: list[str] = []
    for part in path_value.split(os.pathsep):
        if not part:
            continue
        normalized = os.path.normpath(part)
        if normalized.startswith(root_prefix) and normalized.endswith(f"{os.sep}bin"):
            continue
        cleaned.append(part)
    return cleaned


def prepend_unique(path_parts: Iterable[str], first: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for part in [first, *path_parts]:
        if not part or part in seen:
            continue
        seen.add(part)
        result.append(part)
    return result


def build_switch_script(token: str) -> str:
    base_parts = strip_python_install_bins(os.environ.get("PATH", ""))

    normalized = normalize_selector(token)
    if normalized == SYSTEM_SELECTOR:
        path_parts = prepend_unique(base_parts, "/usr/bin")
        python_path = shutil.which("python", path=os.pathsep.join(path_parts)) or "/usr/bin/python"
        version = read_python_version(python_path)
        selector = SYSTEM_SELECTOR
    else:
        runtime = resolve_runtime(normalized)
        path_parts = prepend_unique(base_parts, str(runtime.bin_dir))
        python_path = str(runtime.python_path)
        version = read_python_version(runtime.python_path)
        selector = runtime.selector

    new_path = os.pathsep.join(path_parts)
    message = f"Using {version} ({python_path})"
    return "\n".join(
        [
            f"export PATH={shlex.quote(new_path)}",
            "unset MISE_PYTHON_VERSION",
            f"export PY_SELECTED={shlex.quote(selector)}",
            f"export PY_PYTHON_PATH={shlex.quote(python_path)}",
            "hash -r 2>/dev/null || true",
            f"printf '%s\\n' {shlex.quote(message)}",
        ]
    )


def print_current_python() -> int:
    path = current_python_path()
    if path is None:
        print("python not found", file=sys.stderr)
        return 1
    print(current_python_version())
    print(path)
    return 0


def list_runtimes() -> int:
    active = active_selector()
    rows: list[tuple[str, str, str]] = []

    system_version = read_python_version("/usr/bin/python") if Path("/usr/bin/python").exists() else "missing"
    rows.append((SYSTEM_SELECTOR, "system", f"/usr/bin/python ({system_version})"))

    for runtime in latest_runtimes_by_minor():
        rows.append((runtime.selector, runtime.version, f"{runtime.python_path} ({read_python_version(runtime.python_path)})"))

    selector_width = max(len("selector"), *(len(row[0]) for row in rows))
    target_width = max(len("target"), *(len(row[1]) for row in rows))

    print(f"{'state':<5} {'selector':<{selector_width}} {'target':<{target_width}} python")
    for selector, target, location in rows:
        state = "*" if selector == active else "-"
        print(f"{state:<5} {selector:<{selector_width}} {target:<{target_width}} {location}")
    return 0


def upgrade_app() -> int:
    return subprocess.call([str(install_script_path()), "-u"])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args == ["-h"]:
        print_help()
        return 0
    if args == ["-v"]:
        print(__version__)
        return 0
    if args == ["-u"]:
        return upgrade_app()
    if args == ["ls"]:
        return list_runtimes()
    if args == ["which"]:
        return print_current_python()
    if len(args) == 1:
        try:
            print(build_switch_script(args[0]))
            return 0
        except UsageError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    print("usage: py s | py 312 | py 314 | py ls | py which", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
