"""gtk3_contextmenu.py — right-click context menus for EquipWindow (GTK3 view).

A **mixin** combined into EquipWindow. It reconstructs qdvc-markdown-notebook's
context menus, adapted for assets:

  * Right-click an item in pane 2 (the items list), or a tab label, to raise a
    shared menu:
        Locate in subfolders   (tab only)
        ---
        Open in new tab
        Move to subfolder      (submenu of every folder in the workspace)
        ---
        Copy full path
        Show in file browser

"Locate in subfolders" only appears when the menu is triggered from a tab; it
selects, in pane 1, the folder containing the asset so the user can see where
it lives. "Move to subfolder" lists every folder in the asset's workspace
(plus the workspace root), greying out the one it already sits in, and confirms
before moving the .yml file on disk.

Relies on attributes/handlers defined on the window and its other mixins
(self._workspace_for_root, self._open_asset_in_new_tab, self.refresh_workspaces,
self._icon_menu_item, etc.).
"""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib  # noqa: E402

from . import naming


class ContextMenuMixin:
    """Right-click context menus for EquipWindow (see module docstring)."""

    # ----- entry points ----------------------------------------------------
    def on_items_button_press(self, _widget, event):
        """Right-click on pane 2 → context menu for the row under the pointer.

        We open the menu at the clicked row but do not select it, and return
        True to suppress GTK's default (which would select the row).
        """
        if event.button != 3:
            return False
        path_info = self.item_view.get_path_at_pos(int(event.x), int(event.y))
        if path_info is None:
            return False
        path, _col, _cx, _cy = path_info
        treeiter = self.item_filter.get_iter(path)
        from .gtk3_window import ITEM_PATH, ITEM_WS_ROOT
        asset_path = self.item_filter[treeiter][ITEM_PATH]
        ws_root = self.item_filter[treeiter][ITEM_WS_ROOT]
        menu = self._build_asset_context_menu(
            asset_path, ws_root, include_locate=False)
        menu.popup_at_pointer(event)
        return True

    def on_tab_context_menu(self, tab, event):
        """Right-click on a tab label → the same menu plus 'Locate in
        subfolders' at the top. No-op for a tab with no asset open."""
        if tab.asset is None or tab.asset.path is None:
            return
        ws_root = tab.asset.workspace_root
        menu = self._build_asset_context_menu(
            tab.asset.path, ws_root, include_locate=True)
        menu.popup_at_pointer(event)

    # ----- menu construction ----------------------------------------------
    def _build_asset_context_menu(self, asset_path, ws_root,
                                  include_locate=False):
        menu = Gtk.Menu()

        if include_locate:
            item_locate = self._icon_menu_item("Locate in subfolders",
                                               "edit-find")
            item_locate.connect(
                "activate",
                lambda _i: self._locate_asset_in_panes(asset_path, ws_root))
            menu.append(item_locate)
            menu.append(Gtk.SeparatorMenuItem())

        item_open = self._icon_menu_item("Open in new tab", "tab-new")
        item_open.connect(
            "activate",
            lambda _i: self._open_asset_in_new_tab(asset_path, ws_root))
        menu.append(item_open)

        item_move = self._icon_menu_item("Move to subfolder", "folder-move")
        item_move.set_submenu(self._build_move_submenu(asset_path, ws_root))
        item_move.set_sensitive(self._workspace_for_root(ws_root) is not None)
        menu.append(item_move)

        menu.append(Gtk.SeparatorMenuItem())

        item_copy = self._icon_menu_item("Copy full path", "edit-copy")
        item_copy.connect(
            "activate", lambda _i: self._copy_path_to_clipboard(asset_path))
        menu.append(item_copy)

        item_browse = self._icon_menu_item("Show in file browser",
                                           "system-file-manager")
        item_browse.connect(
            "activate", lambda _i: self._show_in_file_browser(asset_path))
        menu.append(item_browse)

        menu.show_all()
        return menu

    def _build_move_submenu(self, asset_path, ws_root):
        """Submenu of destination folders for 'Move to subfolder'.

        Lists the workspace root plus every folder beneath it. The folder the
        asset already lives in is greyed out. Each lambda binds its destination
        as a default arg so it captures its own value, not the loop's last.
        """
        submenu = Gtk.Menu()
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            mi = Gtk.MenuItem(label="(no workspace)")
            mi.set_sensitive(False)
            submenu.append(mi)
            submenu.show_all()
            return submenu

        cur_dir = os.path.abspath(os.path.dirname(asset_path))
        for dest, label in self._all_folder_destinations(ws):
            mi = Gtk.MenuItem(label=label)
            if os.path.abspath(dest) == cur_dir:
                mi.set_sensitive(False)
            else:
                mi.connect(
                    "activate",
                    lambda _i, d=dest, lbl=label: self._move_asset_to(
                        asset_path, ws_root, d, lbl))
            submenu.append(mi)
        submenu.show_all()
        return submenu

    @staticmethod
    def _all_folder_destinations(ws):
        """Yield (abs_path, display_label) for the root and every folder.

        The root is labelled "(workspace root)"; nested folders use a humanized
        breadcrumb (Kitchen \u2192 Pantry) so duplicate folder names elsewhere in
        the tree stay distinguishable.
        """
        yield (ws.root, "(workspace root)")

        def walk(node, crumbs):
            for child in node.children:
                child_crumbs = crumbs + [child.display_name]
                yield (child.path, "  \u2192  ".join(child_crumbs))
                yield from walk(child, child_crumbs)

        yield from walk(ws.root_node, [])

    # ----- actions ---------------------------------------------------------
    def _locate_asset_in_panes(self, asset_path, ws_root):
        """Select, in pane 1, the folder containing *asset_path*, then fill
        pane 2 with that folder's assets."""
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        folder = os.path.abspath(os.path.dirname(asset_path))
        from .gtk3_window import NAV_PATH
        store = self.nav_store

        target = {"iter": None}

        def match(model, _path, treeiter):
            if os.path.abspath(model[treeiter][NAV_PATH]) == folder:
                target["iter"] = treeiter.copy()
                return True
            return False

        store.foreach(match)
        if target["iter"] is not None:
            tp = store.get_path(target["iter"])
            self.nav_view.expand_to_path(tp)
            self.nav_view.get_selection().select_iter(target["iter"])
            self.nav_view.scroll_to_cell(tp, None, False, 0, 0)

    def _move_asset_to(self, asset_path, ws_root, dest_folder, label):
        name = os.path.basename(asset_path)
        if not self._confirm(
                "Move asset",
                "Move \u201c%s\u201d to %s?" % (name, label)):
            return
        new_path = os.path.join(dest_folder, name)
        if os.path.exists(new_path):
            self._error_dialog("An asset named %s already exists there." % name)
            return
        try:
            os.rename(asset_path, new_path)
        except OSError as exc:
            self._error_dialog("Could not move asset: %s" % exc)
            return
        # Update any open tab pointing at the moved file.
        old_abs = os.path.abspath(asset_path)
        ws = self._workspace_for_root(ws_root)
        for tab in self.tabs:
            if (tab.asset is not None and tab.asset.path is not None
                    and os.path.abspath(tab.asset.path) == old_abs):
                tab.asset.path = new_path
                tab.workspace_disp = ws.display_name if ws else ""
                tab.refresh_title()
        if ws is not None:
            ws.refresh()
        self.refresh_workspaces()
        self.set_status("Moved %s to %s" % (name, label))

    def _copy_path_to_clipboard(self, path):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(path, -1)
        clipboard.store()
        self.set_status("Copied path to clipboard")

    def _show_in_file_browser(self, path):
        folder = os.path.dirname(path)
        uri = GLib.filename_to_uri(folder, None)
        try:
            Gtk.show_uri_on_window(self, uri, Gdk.CURRENT_TIME)
        except GLib.Error as exc:
            self._error_dialog("Could not open file browser: %s" % exc)

    # ----- small dialog helpers -------------------------------------------
    def _confirm(self, title, body):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
        dlg.format_secondary_text(body)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.OK

    def _error_dialog(self, message):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=message)
        dlg.run()
        dlg.destroy()
