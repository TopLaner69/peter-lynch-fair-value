#!/bin/zsh
# Builds Peter Lynch Fair Value.app from source and installs it in /Applications.
# Usage: ./install.sh   (run from anywhere; requires Homebrew python@3.14 + python-tk@3.14)

set -euo pipefail

APP_NAME="Peter Lynch Fair Value"
DEST="/Applications/$APP_NAME.app"
cd "$(dirname "$0")"

step() { print -P "\n%F{yellow}==>%f %B$1%b"; }
fail() { print -P "%F{red}Error:%f $1" >&2; exit 1; }

[[ "$(uname)" == "Darwin" ]] || fail "this app can only be built on macOS."

step "Looking for Python 3.14"
PYTHON=""
for candidate in python3.14 /opt/homebrew/bin/python3.14 /usr/local/bin/python3.14; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done
[[ -n "$PYTHON" ]] || fail "Python 3.14 not found. Install it with:
    brew install python@3.14 python-tk@3.14"
"$PYTHON" -c "import tkinter" 2>/dev/null || fail "Python has no Tk support. Install it with:
    brew install python-tk@3.14"
echo "Using $PYTHON"

step "Creating the build environment (.venv)"
[[ -x .venv/bin/python ]] || "$PYTHON" -m venv .venv
.venv/bin/pip install --quiet --require-hashes -r requirements-build.txt

step "Running the tests"
.venv/bin/python -m unittest --quiet test_lynch

step "Building the app"
rm -rf build dist
.venv/bin/python setup.py py2app >build.log 2>&1 || fail "the build failed; see build.log"
rm -f build.log

step "Installing into /Applications"
if pgrep -f "$DEST/Contents/MacOS/" >/dev/null; then
    osascript -e "tell application \"$APP_NAME\" to quit" >/dev/null 2>&1 || true
    sleep 2
fi
rm -rf "$DEST"
ditto "dist/$APP_NAME.app" "$DEST"
touch "$DEST"  # refreshes the icon in Finder and the Dock

print -P "\n%F{green}Done!%f $APP_NAME is installed in /Applications."
echo "Open it from Launchpad or Spotlight (⌘Space → \"Peter Lynch\")."
