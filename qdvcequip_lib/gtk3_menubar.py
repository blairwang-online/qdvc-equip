"""gtk3_menubar.py — GTK3 menu-bar construction for EquipWindow.

A **mixin** holding only menu-building methods, factored out of the window for
readability (mirroring qdvc-markdown-notebook's structure). It is combined into
EquipWindow in gtk3_window.py and relies on attributes/handlers defined there
and in the other mixins (e.g. self.on_new_asset, self.settings). No standalone
behaviour; GTK3-specific.

GTK notes for non-GTK readers:
  * A Gtk.MenuBar holds top-level Gtk.MenuItems; each gets a submenu (a
    Gtk.Menu) via set_submenu(). "activate" fires when an item is chosen.
  * Shortcuts go through an "accel group" registered on the window; each item
    calls add_accelerator(signal, group, key, modifiers, flags).
  * new_with_mnemonic("_File") makes the letter after "_" the Alt-access key.
  * Gtk.ImageMenuItem (deprecated but idiomatic for this MATE-era look) puts a
    leading icon beside the label — see _icon_menu_item.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk  # noqa: E402


class MenuBarMixin:
    """Menu-bar construction for EquipWindow (see module docstring)."""

    def _build_menubar(self):
        menubar = Gtk.MenuBar()
        accel = Gtk.AccelGroup()
        self.add_accel_group(accel)
        self._accel_group = accel

        # ---- File menu ----
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem.new_with_mnemonic("_File")
        file_item.set_submenu(file_menu)

        mi_new_asset = self._icon_menu_item("New asset", "document-new")
        mi_new_asset.add_accelerator("activate", accel, Gdk.KEY_n,
                                     Gdk.ModifierType.CONTROL_MASK,
                                     Gtk.AccelFlags.VISIBLE)
        mi_new_asset.connect("activate", self.on_new_asset)
        file_menu.append(mi_new_asset)

        mi_save = self._icon_menu_item("Save asset", "document-save")
        mi_save.add_accelerator("activate", accel, Gdk.KEY_s,
                                Gdk.ModifierType.CONTROL_MASK,
                                Gtk.AccelFlags.VISIBLE)
        mi_save.connect("activate", self.on_save_asset)
        file_menu.append(mi_save)

        file_menu.append(Gtk.SeparatorMenuItem())

        mi_open = self._icon_menu_item("Open workspace\u2026", "folder-open")
        mi_open.add_accelerator("activate", accel, Gdk.KEY_o,
                                Gdk.ModifierType.CONTROL_MASK,
                                Gtk.AccelFlags.VISIBLE)
        mi_open.connect("activate", self.on_open_workspace)
        file_menu.append(mi_open)

        mi_close_ws = self._icon_menu_item("Close workspace", "window-close")
        mi_close_ws.connect("activate", self.on_close_workspace)
        file_menu.append(mi_close_ws)

        # "Open recent" submenu, populated dynamically from settings.
        self.recent_menu_item = self._icon_menu_item(
            "Open recent", "document-open-recent")
        self.recent_menu = Gtk.Menu()
        self.recent_menu_item.set_submenu(self.recent_menu)
        file_menu.append(self.recent_menu_item)

        file_menu.append(Gtk.SeparatorMenuItem())

        # New tab sits immediately before Close tab (per the spec).
        mi_new_tab = self._icon_menu_item("New tab", "tab-new")
        mi_new_tab.add_accelerator("activate", accel, Gdk.KEY_t,
                                   Gdk.ModifierType.CONTROL_MASK,
                                   Gtk.AccelFlags.VISIBLE)
        mi_new_tab.connect("activate", self.on_new_tab)
        file_menu.append(mi_new_tab)

        mi_close_tab = self._icon_menu_item("Close tab", "window-close")
        mi_close_tab.add_accelerator("activate", accel, Gdk.KEY_w,
                                     Gdk.ModifierType.CONTROL_MASK,
                                     Gtk.AccelFlags.VISIBLE)
        mi_close_tab.connect("activate", self.on_close_tab)
        file_menu.append(mi_close_tab)

        file_menu.append(Gtk.SeparatorMenuItem())

        mi_quit = self._icon_menu_item("Quit", "application-exit")
        mi_quit.add_accelerator("activate", accel, Gdk.KEY_q,
                                Gdk.ModifierType.CONTROL_MASK,
                                Gtk.AccelFlags.VISIBLE)
        mi_quit.connect("activate", self.on_quit)
        file_menu.append(mi_quit)

        menubar.append(file_item)

        # ---- Edit menu ----
        edit_menu = Gtk.Menu()
        edit_item = Gtk.MenuItem.new_with_mnemonic("_Edit")
        edit_item.set_submenu(edit_menu)

        mi_new_folder = self._icon_menu_item("New folder\u2026", "folder-new")
        mi_new_folder.connect("activate", self.on_new_folder)
        edit_menu.append(mi_new_folder)

        mi_refresh = self._icon_menu_item("Refresh workspaces", "view-refresh")
        mi_refresh.add_accelerator("activate", accel, Gdk.KEY_F5, 0,
                                   Gtk.AccelFlags.VISIBLE)
        mi_refresh.connect("activate", self.on_refresh)
        edit_menu.append(mi_refresh)

        edit_menu.append(Gtk.SeparatorMenuItem())

        mi_prefs = self._icon_menu_item("Preferences", "preferences-system")
        mi_prefs.connect("activate", self.on_preferences)
        edit_menu.append(mi_prefs)

        menubar.append(edit_item)

        # ---- View menu ----
        view_menu = Gtk.Menu()
        view_item = Gtk.MenuItem.new_with_mnemonic("_View")
        view_item.set_submenu(view_menu)

        # Guard flag preventing the menu<->toolbar toggle sync from looping.
        self._syncing_view_toggles = False

        self.mi_toolbar = Gtk.CheckMenuItem(label="Toolbar")
        self.mi_toolbar.set_active(bool(self.settings["show_toolbar"]))
        self.mi_toolbar.connect("toggled", self.on_toggle_toolbar)
        view_menu.append(self.mi_toolbar)

        self.mi_statusbar = Gtk.CheckMenuItem(label="Statusbar")
        self.mi_statusbar.set_active(bool(self.settings["show_statusbar"]))
        self.mi_statusbar.connect("toggled", self.on_toggle_statusbar)
        view_menu.append(self.mi_statusbar)

        view_menu.append(Gtk.SeparatorMenuItem())

        self.mi_cardview = Gtk.CheckMenuItem(label="Card view")
        self.mi_cardview.add_accelerator("activate", accel, Gdk.KEY_d,
                                         Gdk.ModifierType.CONTROL_MASK,
                                         Gtk.AccelFlags.VISIBLE)
        self.mi_cardview.connect("toggled", self.on_menu_toggle_card_view)
        view_menu.append(self.mi_cardview)

        self.mi_readonly = Gtk.CheckMenuItem(label="Read-only")
        self.mi_readonly.set_active(self.read_only)
        self.mi_readonly.add_accelerator("activate", accel, Gdk.KEY_e,
                                         Gdk.ModifierType.CONTROL_MASK,
                                         Gtk.AccelFlags.VISIBLE)
        self.mi_readonly.connect("toggled", self.on_menu_toggle_read_only)
        view_menu.append(self.mi_readonly)

        self.mi_preview = Gtk.CheckMenuItem(label="Preview")
        self.mi_preview.add_accelerator("activate", accel, Gdk.KEY_grave,
                                        Gdk.ModifierType.CONTROL_MASK,
                                        Gtk.AccelFlags.VISIBLE)
        self.mi_preview.connect("toggled", self.on_menu_toggle_preview)
        view_menu.append(self.mi_preview)

        menubar.append(view_item)

        # ---- Help menu ----
        help_menu = Gtk.Menu()
        help_item = Gtk.MenuItem.new_with_mnemonic("_Help")
        help_item.set_submenu(help_menu)

        mi_about = self._icon_menu_item("About", "help-about")
        mi_about.connect("activate", self.on_about)
        help_menu.append(mi_about)

        menubar.append(help_item)
        return menubar

    @staticmethod
    def _icon_menu_item(label, icon_name):
        """Build a menu item with a leading icon, GNOME2/MATE style.

        Uses Gtk.ImageMenuItem (deprecated in GTK3 but the idiomatic way to get
        icons in menus, and a good fit for this app's MATE-era look). Falls back
        to a plain MenuItem if ImageMenuItem is unavailable on the running build.
        """
        try:
            item = Gtk.ImageMenuItem(label=label)
            img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            item.set_image(img)
            item.set_always_show_image(True)
            return item
        except (AttributeError, TypeError):
            return Gtk.MenuItem(label=label)
