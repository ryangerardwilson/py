# py Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Documents/agent_context/CLI_TUI_STYLE_GUIDE.md` for CLI taste and help shape.
- Follow `/home/ryan/Documents/agent_context/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` for launcher, installer, and release behavior.

## Scope
- `py` is a shell-first Python selector.
- Keep the primary interaction compact:
  - `py s`
  - `py 312`
  - `py 314`
  - `py ls`
  - `py which`
- Do not expand this into a general package manager, virtualenv manager, or project environment tool unless the user explicitly asks.

## Backend
- Treat installed `mise` Python runtimes under `~/.local/share/mise/installs/python/` as the backend inventory.
- Do not mutate `/usr/bin/python` or attempt to replace the system interpreter.
- Prefer changing shell PATH precedence over trying to patch the parent shell indirectly from a subprocess.

## Shell Integration
- The user-facing `py` command must work inside an interactive shell.
- Keep the shell hook in `shell/py.bash` and let the installer print the exact manual shell line the user should add.
- The CLI should emit shell code for selector actions; the shell hook is responsible for `eval`-ing it.
- Keep help/version/upgrade/list/which behavior directly executable without shell magic.

## Config
- `py` does not own a user-editable config file right now.
- Do not add a `conf` command unless the app later grows real user-facing config.
