# py

Shell-first Python selector for switching the current shell between system Python and installed `mise` runtimes.

## Install

```bash
./install.sh
```

Or install from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/py/main/install.sh | bash
```

After install, open a new shell or run:

```bash
source ~/.bashrc
```

## Usage

```bash
py -h
py -v
py -u

py s
py 312
py 314

py ls
py which
```

`py s` moves `/usr/bin/python` ahead of any installed `mise` Python runtime.

`py 312` and `py 314` select the latest installed `3.12.x` and `3.14.x` runtime from:

```text
~/.local/share/mise/installs/python/
```

If a requested runtime is missing, `py` tells you which `mise install python@...` command to run.

## Release

This repo follows the workspace CLI contract:

```bash
./push_release_upgrade.sh
```

That script pushes the current branch, tags the next release, waits for the GitHub release asset, and upgrades the installed app.
