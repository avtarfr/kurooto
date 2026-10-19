#!/bin/sh
# Kurooto installer for macOS and Linux. Paste this in a terminal:
#     curl -LsSf https://avtarfr.github.io/kurooto/install.sh | sh
# It installs uv (a small Python manager), Python 3.12 and Kurooto for your user only (no sudo),
# turns on start-at-login, starts Kurooto, and opens the setup page in your browser.
# Run it again any time to repair or update. Uninstall: kurooto uninstall
set -eu
UV_VERSION=0.13.1
say() { printf '  %s\n' "$*"; }
printf '\n  \033[35mKUROOTO\033[0m\n'
say "Setting up your assistant. This takes a few minutes the first time."

# 1. room on the disk (in KB)
free_kb=$(df -Pk "$HOME" | awk 'NR==2 {print $4}')
if [ "${free_kb:-0}" -lt 2097152 ]; then
  say "Only $((free_kb / 1048576)) GB free in your home folder. Kurooto needs at least 2 GB to install."
  exit 1
fi
say "Free space: $((free_kb / 1048576)) GB. Fine."

# 2. uv (installs Python for us), pinned version, for this user only
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv $UV_VERSION..."
  if command -v curl >/dev/null 2>&1; then curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | sh >/dev/null
  else wget -qO- "https://astral.sh/uv/$UV_VERSION/install.sh" | sh >/dev/null; fi
fi

# 3. Python 3.12, then Kurooto: bootstrap.py checks the release signature and every file's checksum first
say "Installing Python 3.12..."
uv python install 3.12 >/dev/null
tmp="${TMPDIR:-/tmp}/kurooto-bootstrap-$$.py"
if [ -n "${KUROOTO_SOURCE:-}" ]; then
  cp "$KUROOTO_SOURCE/installer/bootstrap.py" "$tmp"
  uv run --no-project --python 3.12 --with 'cryptography>=43' "$tmp" --source "$KUROOTO_SOURCE"
else
  base="${KUROOTO_UPDATE_BASE:-https://avtarfr.github.io/kurooto}"
  if command -v curl >/dev/null 2>&1; then curl -fsSL "$base/bootstrap.py" -o "$tmp"; else wget -qO "$tmp" "$base/bootstrap.py"; fi
  uv run --no-project --python 3.12 --with 'cryptography>=43' "$tmp"
fi
rm -f "$tmp"
printf '\n'
say "Done. If the setup page didn't open, run:  kurooto open"
say "Kurooto keeps running in the background and starts when you log in. Open a new terminal to use the kurooto command."
