#!/usr/bin/env python3
"""
main.py — Entry point for ContactVault.

Usage:
    python main.py

Keyboard shortcuts:
    Ctrl+N  → Add new contact
    Ctrl+F  → Focus search bar
    Ctrl+E  → Export to CSV
    Ctrl+T  → Toggle dark/light theme
    Delete  → Delete selected contact
    F5      → Refresh view
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

try:
    import customtkinter  # noqa: F401
except ImportError:
    print("ERROR: customtkinter is not installed.")
    print("Run:  pip install customtkinter pillow openpyxl")
    sys.exit(1)

from ui import run

if __name__ == "__main__":
    run()
