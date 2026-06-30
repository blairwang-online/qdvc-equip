#!/usr/bin/env python3
"""qdvc_equip.py

QDVC Equip \u2014 a three-pane desktop tracker for your tools, equipment, and
materials, built with GTK 3 via PyGObject for a MATE / GNOME2-era look and feel.

Usage:
    python3 qdvc_equip.py /path/to/workspace [/path/to/another ...]
    python3 qdvc_equip.py            # reopen last session, or Ctrl+O to open

This file is a thin entry point. Application logic lives in the qdvcequip_lib
package: GTK-free core modules (naming, asset, workspace, settings) and the
GTK3 view/controller modules (prefaced gtk3_). See MAINTENANCE.md.
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402

from qdvcequip_lib import __app_id__
from qdvcequip_lib.gtk3_window import EquipWindow


def main():
    # Give the process a stable program name so the window manager can match
    # our windows to the .desktop file (StartupWMClass=qdvc-equip).
    GLib.set_prgname(__app_id__)
    # Default window/taskbar icon (a generic freedesktop package icon).
    Gtk.Window.set_default_icon_name("package-x-generic")

    workspace_paths = sys.argv[1:] or None
    win = EquipWindow(workspace_paths=workspace_paths)
    win.show_all()
    # Respect persisted visibility toggles after show_all().
    win.toolbar.set_visible(bool(win.settings["show_toolbar"]))
    win.statusbar.set_visible(bool(win.settings["show_statusbar"]))
    Gtk.main()


if __name__ == "__main__":
    main()
