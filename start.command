#!/bin/zsh
# Double-click in Finder to start the app.
cd "$(dirname "$0")"
exec /opt/homebrew/bin/python3.14 app.py
