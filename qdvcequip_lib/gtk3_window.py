"""gtk3_window.py — the main application window (GTK3 view/controller).

Assembles the GNOME2-era layout and wires user actions to the GTK-free core.
The window is deliberately thin: it defines `EquipWindow` as a composition of
focused mixins and holds only construction/session bootstrap in `__init__`.
Everything else lives in a sibling `gtk3_` mixin:

  * gtk3_panes.PanesMixin        — layout, the three panes, status bar, and the
                                   pane-1/pane-2 cell rendering (incl. genre
                                   icons).
  * gtk3_tabs.TabsMixin          — the pane-3 notebook: tab lifecycle,
                                   editor/preview rendering, editor styling, and
                                   tab-switch → toggle sync.
  * gtk3_actions.ActionsMixin    — workspace management, item-list filling,
                                   selection/search/Alt+N nav, all menu/toolbar
                                   action handlers, the view toggles, and small
                                   helpers (prompt, recent menu, status bar).
  * gtk3_menubar.MenuBarMixin    — the File/Edit/View/Help menus.
  * gtk3_toolbar.ToolbarMixin    — the toolbar + toolbar_style handling.
  * gtk3_contextmenu.ContextMenuMixin — the pane-2 and tab right-click menus.

Shared TreeStore/ListStore column indices and node-kind tags live in
gtk3_common (and are re-exported here for backward compatibility). Each
AssetTab (gtk3_editortab) owns its editor view, label, and per-tab state.

Per-tab modes: Read-only and Preview are tracked per tab (like
qdvc-markdown-notebook). The toolbar/menu toggles act on the active tab, and
switching tabs reflects that tab's state back onto the toggles. Activating
Preview disables the Read-only toggle (preview is read-only by construction).
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk  # noqa: E402

from . import __app_name__
from .settings import Settings
from .gtk3_menubar import MenuBarMixin
from .gtk3_toolbar import ToolbarMixin
from .gtk3_contextmenu import ContextMenuMixin
from .gtk3_panes import PanesMixin
from .gtk3_tabs import TabsMixin
from .gtk3_actions import ActionsMixin

# Re-export the shared constants so existing importers (and tests) that did
# `from qdvcequip_lib.gtk3_window import KIND_TAGGED` keep working.
from .gtk3_common import (  # noqa: F401
    NAV_LABEL, NAV_KIND, NAV_PATH, NAV_WS_ROOT,
    KIND_ALL, KIND_WORKSPACE, KIND_FOLDER,
    KIND_TAGS_ROOT, KIND_TAGGED, KIND_UNTAGGED,
    KIND_GENRE_ROOT, KIND_GENRE, KIND_WORKSPACES_ROOT,
    NO_GENRE_SENTINEL,
    ITEM_LABEL, ITEM_PATH, ITEM_WS_ROOT, ITEM_TAG, ITEM_SNIPPET, ITEM_GENRE,
)


class EquipWindow(MenuBarMixin, ToolbarMixin, ContextMenuMixin,
                  PanesMixin, TabsMixin, ActionsMixin, Gtk.Window):
    """Top-level QDVC Equip window (a composition of the gtk3_ mixins)."""

    def __init__(self, workspace_paths=None):
        super().__init__(title=__app_name__)
        self.set_default_size(1100, 680)
        # Center on screen at startup (like qdvc-markdown-notebook) rather than
        # letting the window manager place us in its default corner.
        self.set_position(Gtk.WindowPosition.CENTER)

        self.settings = Settings.load()
        self.workspaces = []            # list[Workspace]
        # Window-level mirrors of the ACTIVE tab's per-tab state, read by the
        # status bar and the gating logic.
        self.read_only = bool(self.settings["read_only"])
        self.preview_mode = False
        self.card_view = False
        self.tabs = []                  # list[AssetTab]
        self._last_status = "Ready"

        self._build_ui()
        self._apply_view_settings()

        to_open = list(workspace_paths or [])
        if not to_open:
            to_open = list(self.settings["open_workspaces"])
        for path in to_open:
            if os.path.isdir(os.path.expanduser(path)):
                self.open_workspace(path, persist=False)

        if not self.tabs:
            self.new_tab()
        self._rebuild_recent_menu()
        # Don't let the first toolbar button take initial keyboard focus (it
        # would show a focus ring on startup otherwise); focus the nav tree
        # instead, like qdvc-markdown-notebook.
        self.set_focus(self.nav_view)
        self.connect("destroy", self.on_destroy)
        # Tab navigation shortcuts (Alt+1 .. Alt+9), like the notebook.
        self.connect("key-press-event", self._on_key_press)
