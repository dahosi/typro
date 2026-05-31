#!/bin/bash
# Double-clickable launcher for macOS.
# Opens Typro from this file's own folder, preferring a modern Python.
#
# Apple's built-in Python uses an outdated Tk that crashes on modern macOS,
# so we look for a Homebrew Python (Tk 8.6+) first and fall back to python3.
cd "$(dirname "$0")"

for PY in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3 \
          /usr/local/bin/python3 python3; do
    if command -v "$PY" >/dev/null 2>&1; then
        "$PY" typro.py
        exit $?
    fi
done

echo "No Python 3 found. Install it (e.g. 'brew install python-tk') and retry."
read -r -p "Press Return to close..."
