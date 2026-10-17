#!/bin/zsh
# Dublu-click în Finder pentru a porni aplicația.
cd "$(dirname "$0")"
exec /opt/homebrew/bin/python3.14 app.py
