"""gtk3_window.py — the main application window (GTK3 view/controller).

Assembles the GNOME2-era layout: a menubar (File / Edit / View / Help with
Alt-mnemonics), a toolbar (New tab / New asset / Save asset / Card view /
Read-only / Preview), three horizontal panes (navigation tree, item list, item
details) inside nested paned widgets, and a status bar.

Multi-workspace support: the navigation tree (pane 1) holds one expandable
root per open workspace, each rendering the full nested folder hierarchy.
Selecting a folder fills the item list (pane 2) with the assets directly under
it; selecting an asset opens it in the active tab of the details notebook
(pane 3). Each tab shows either the plaintext YAML editor or, when Preview is
on, the rendered card from gtk3_preview.

Read-only and Preview are app-wide toggles mirrored between the toolbar and the
View menu, matching the reference notebook's behaviour.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango  # noqa: E402

from . import __version__, __app_name__
from .workspace import Workspace
from .settings import Settings
from .asset import Asset
from . import naming
from .gtk3_preview import build_preview

# Navigation tree column indices.
NAV_LABEL, NAV_KIND, NAV_PATH, NAV_WS_ROOT = range(4)
# kinds:
KIND_WORKSPACE = "workspace"
KIND_FOLDER = "folder"
# Item list column indices.
ITEM_LABEL, ITEM_PATH, ITEM_WS_ROOT = range(3)


class AssetTab(object):
    """State for one tab in the details notebook (pane 3)."""

    def __init__(self):
        self.asset = None            # Asset or None
        self.workspace_disp = ""     # workspace display name for breadcrumb
        self.container = None        # Gtk.Box swapped between editor/preview
        self.textview = None         # Gtk.TextView (plaintext editor)
        self.scroller = None         # ScrolledWindow holding the textview
        self.label = None            # Gtk.Label in the tab header
        self.dirty = False


class EquipWindow(Gtk.Window):
    """Top-level QDVC Equip window."""

    def __init__(self, workspace_paths=None):
        super().__init__(title=__app_name__)
        self.set_default_size(1100, 680)

        self.settings = Settings.load()
        self.workspaces = []            # list[Workspace]
        self.read_only = bool(self.settings["read_only"])
        self.preview_on = False
        self.tabs = []                  # list[AssetTab]

        self._build_ui()
        self._apply_view_settings()

        # Open workspaces from CLI args, else from persisted session.
        to_open = list(workspace_paths or [])
        if not to_open:
            to_open = list(self.settings["open_workspaces"])
        for path in to_open:
            if os.path.isdir(os.path.expanduser(path)):
                self.open_workspace(path, persist=False)

        if not self.tabs:
            self.new_tab()
        self.connect("destroy", self.on_destroy)

    # ====================================================================
    # UI construction
    # ====================================================================
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        self.accels = Gtk.AccelGroup()
        self.add_accel_group(self.accels)

        root.pack_start(self._build_menubar(), False, False, 0)
        self.toolbar = self._build_toolbar()
        root.pack_start(self.toolbar, False, False, 0)

        # Three panes via nested Gtk.Paned.
        self.outer_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.inner_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.outer_paned.pack1(self._build_nav_pane(), resize=False, shrink=False)
        self.inner_paned.pack1(self._build_item_pane(), resize=True, shrink=False)
        self.inner_paned.pack2(self._build_details_pane(), resize=True, shrink=False)
        self.outer_paned.pack2(self.inner_paned, resize=True, shrink=False)
        self.outer_paned.set_position(260)
        self.inner_paned.set_position(280)
        root.pack_start(self.outer_paned, True, True, 0)

        # Status bar.
        self.statusbar = Gtk.Statusbar()
        self._status_ctx = self.statusbar.get_context_id("main")
        root.pack_start(self.statusbar, False, False, 0)
        self._refresh_status()

    # ----- menubar ---------------------------------------------------------
    def _build_menubar(self):
        menubar = Gtk.MenuBar()

        # File
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem.new_with_mnemonic("_File")
        file_item.set_submenu(file_menu)
        self._menu_item(file_menu, "_New tab", self.on_new_tab,
                        key=Gdk.KEY_t, mod=Gdk.ModifierType.CONTROL_MASK)
        self._menu_item(file_menu, "New _asset", self.on_new_asset,
                        key=Gdk.KEY_n, mod=Gdk.ModifierType.CONTROL_MASK)
        self._menu_item(file_menu, "_Save asset", self.on_save_asset,
                        key=Gdk.KEY_s, mod=Gdk.ModifierType.CONTROL_MASK)
        file_menu.append(Gtk.SeparatorMenuItem())
        self._menu_item(file_menu, "_Open workspace\u2026", self.on_open_workspace,
                        key=Gdk.KEY_o, mod=Gdk.ModifierType.CONTROL_MASK)
        self._menu_item(file_menu, "_Close workspace", self.on_close_workspace)
        self.recent_menu_item = Gtk.MenuItem.new_with_mnemonic("Open _recent")
        self.recent_menu = Gtk.Menu()
        self.recent_menu_item.set_submenu(self.recent_menu)
        file_menu.append(self.recent_menu_item)
        self._rebuild_recent_menu()
        file_menu.append(Gtk.SeparatorMenuItem())
        self._menu_item(file_menu, "Close _tab", self.on_close_tab,
                        key=Gdk.KEY_w, mod=Gdk.ModifierType.CONTROL_MASK)
        self._menu_item(file_menu, "_Quit", lambda *_: self.close(),
                        key=Gdk.KEY_q, mod=Gdk.ModifierType.CONTROL_MASK)
        menubar.append(file_item)

        # Edit
        edit_menu = Gtk.Menu()
        edit_item = Gtk.MenuItem.new_with_mnemonic("_Edit")
        edit_item.set_submenu(edit_menu)
        self._menu_item(edit_menu, "_New folder\u2026", self.on_new_folder)
        self._menu_item(edit_menu, "_Refresh workspaces", self.on_refresh,
                        key=Gdk.KEY_F5, mod=0)
        menubar.append(edit_item)

        # View
        view_menu = Gtk.Menu()
        view_item = Gtk.MenuItem.new_with_mnemonic("_View")
        view_item.set_submenu(view_menu)
        self.mi_toolbar = Gtk.CheckMenuItem.new_with_mnemonic("Show _Toolbar")
        self.mi_toolbar.set_active(bool(self.settings["show_toolbar"]))
        self.mi_toolbar.connect("toggled", self.on_toggle_toolbar)
        view_menu.append(self.mi_toolbar)
        self.mi_statusbar = Gtk.CheckMenuItem.new_with_mnemonic("Show _Statusbar")
        self.mi_statusbar.set_active(bool(self.settings["show_statusbar"]))
        self.mi_statusbar.connect("toggled", self.on_toggle_statusbar)
        view_menu.append(self.mi_statusbar)
        view_menu.append(Gtk.SeparatorMenuItem())
        self.mi_readonly = Gtk.CheckMenuItem.new_with_mnemonic("_Read-only")
        self.mi_readonly.set_active(self.read_only)
        self.mi_readonly.connect("toggled", self.on_menu_readonly)
        view_menu.append(self.mi_readonly)
        self.mi_preview = Gtk.CheckMenuItem.new_with_mnemonic("_Preview")
        self.mi_preview.set_active(self.preview_on)
        self.mi_preview.connect("toggled", self.on_menu_preview)
        view_menu.append(self.mi_preview)
        menubar.append(view_item)

        # Help
        help_menu = Gtk.Menu()
        help_item = Gtk.MenuItem.new_with_mnemonic("_Help")
        help_item.set_submenu(help_menu)
        self._menu_item(help_menu, "_About", self.on_about)
        menubar.append(help_item)

        return menubar

    def _menu_item(self, menu, label, handler, key=None, mod=None):
        item = Gtk.MenuItem.new_with_mnemonic(label)
        item.connect("activate", handler)
        if key is not None:
            item.add_accelerator(
                "activate", self.accels, key, mod or 0,
                Gtk.AccelFlags.VISIBLE,
            )
        menu.append(item)
        return item

    # ----- toolbar ----------------------------------------------------------
    def _build_toolbar(self):
        tb = Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.BOTH_HORIZ)

        def tool_button(label, icon, handler, tip):
            btn = Gtk.ToolButton()
            btn.set_label(label)
            btn.set_icon_name(icon)
            btn.set_is_important(True)
            btn.set_tooltip_text(tip)
            btn.connect("clicked", handler)
            tb.insert(btn, -1)
            return btn

        def toggle_button(label, icon, handler, tip, active=False):
            btn = Gtk.ToggleToolButton()
            btn.set_label(label)
            btn.set_icon_name(icon)
            btn.set_is_important(True)
            btn.set_tooltip_text(tip)
            btn.set_active(active)
            handler_id = btn.connect("toggled", handler)
            tb.insert(btn, -1)
            return btn, handler_id

        tool_button("New tab", "tab-new", self.on_new_tab, "Open a new tab")
        tool_button("New asset", "document-new", self.on_new_asset,
                    "Create a new asset")
        tool_button("Save asset", "document-save", self.on_save_asset,
                    "Save the current asset")
        tb.insert(Gtk.SeparatorToolItem(), -1)
        self.tb_cardview, self.tb_cardview_hid = toggle_button(
            "Card view", "view-grid-symbolic", self.on_toggle_cardview,
            "Show the item list as cards")
        self.tb_readonly, self.tb_readonly_hid = toggle_button(
            "Read-only", "changes-prevent-symbolic", self.on_toolbar_readonly,
            "Toggle read-only mode (applies to all tabs)",
            active=self.read_only)
        self.tb_preview, self.tb_preview_hid = toggle_button(
            "Preview", "view-reveal-symbolic", self.on_toolbar_preview,
            "Render the asset as a card instead of YAML text")
        return tb

    # ----- pane 1: navigation tree -----------------------------------------
    def _build_nav_pane(self):
        frame = Gtk.Frame()
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        # columns: label, kind, path, ws_root
        self.nav_store = Gtk.TreeStore(str, str, str, str)
        self.nav_view = Gtk.TreeView(model=self.nav_store)
        self.nav_view.set_headers_visible(False)
        col = Gtk.TreeViewColumn("Workspaces")
        icon = Gtk.CellRendererPixbuf()
        col.pack_start(icon, False)
        col.set_cell_data_func(icon, self._nav_icon_func)
        text = Gtk.CellRendererText()
        col.pack_start(text, True)
        col.add_attribute(text, "text", NAV_LABEL)
        self.nav_view.append_column(col)
        self.nav_view.get_selection().connect("changed", self.on_nav_selected)
        sw.add(self.nav_view)
        frame.add(sw)
        return frame

    def _nav_icon_func(self, _col, cell, model, it, _data):
        kind = model[it][NAV_KIND]
        if kind == KIND_WORKSPACE:
            cell.set_property("icon-name", "drive-harddisk")
        else:
            cell.set_property("icon-name", "folder")

    # ----- pane 2: item list -----------------------------------------------
    def _build_item_pane(self):
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Filter assets\u2026")
        self.search_entry.connect("search-changed", self.on_filter_changed)
        box.pack_start(self.search_entry, False, False, 2)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.item_store = Gtk.ListStore(str, str, str)  # label, path, ws_root
        self.item_filter = self.item_store.filter_new()
        self.item_filter.set_visible_func(self._item_visible_func)
        self.item_view = Gtk.TreeView(model=self.item_filter)
        self.item_view.set_headers_visible(False)
        col = Gtk.TreeViewColumn("Asset")
        icon = Gtk.CellRendererPixbuf()
        icon.set_property("icon-name", "package-x-generic")
        col.pack_start(icon, False)
        text = Gtk.CellRendererText()
        col.pack_start(text, True)
        col.add_attribute(text, "text", ITEM_LABEL)
        self.item_view.append_column(col)
        self.item_view.get_selection().connect("changed", self.on_item_selected)
        self.item_view.connect("row-activated", self.on_item_activated)
        sw.add(self.item_view)
        box.pack_start(sw, True, True, 0)
        frame.add(box)
        return frame

    def _item_visible_func(self, model, it, _data):
        term = self.search_entry.get_text().strip().lower()
        if not term:
            return True
        return term in (model[it][ITEM_LABEL] or "").lower()

    # ----- pane 3: details notebook ----------------------------------------
    def _build_details_pane(self):
        frame = Gtk.Frame()
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.connect("switch-page", self.on_tab_switched)
        frame.add(self.notebook)
        return frame

    # ====================================================================
    # Workspace management
    # ====================================================================
    def open_workspace(self, path, persist=True):
        path = os.path.abspath(os.path.expanduser(path))
        for ws in self.workspaces:
            if ws.root == path:
                self.set_status("Workspace already open: %s" % ws.display_name)
                return ws
        ws = Workspace(path)
        self.workspaces.append(ws)
        self._add_workspace_to_nav(ws)
        if persist:
            self.settings.note_opened(path)
            self.settings.save()
            self._rebuild_recent_menu()
        self.set_status("Opened workspace: %s" % ws.display_name)
        return ws

    def _add_workspace_to_nav(self, ws):
        ws_iter = self.nav_store.append(
            None, [ws.display_name, KIND_WORKSPACE, ws.root, ws.root]
        )
        self._populate_folder_children(ws_iter, ws.root_node, ws.root)
        self.nav_view.expand_row(self.nav_store.get_path(ws_iter), False)

    def _populate_folder_children(self, parent_iter, node, ws_root):
        for child in node.children:
            child_iter = self.nav_store.append(
                parent_iter,
                [child.display_name, KIND_FOLDER, child.path, ws_root],
            )
            self._populate_folder_children(child_iter, child, ws_root)

    def _workspace_for_root(self, ws_root):
        for ws in self.workspaces:
            if ws.root == ws_root:
                return ws
        return None

    def refresh_workspaces(self):
        # Remember which folder was selected, rebuild, then try to reselect.
        self.nav_store.clear()
        for ws in self.workspaces:
            ws.refresh()
            self._add_workspace_to_nav(ws)

    # ====================================================================
    # Tabs (pane 3)
    # ====================================================================
    def new_tab(self, asset=None, workspace_disp=""):
        tab = AssetTab()
        tab.asset = asset
        tab.workspace_disp = workspace_disp

        tab.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        tab.scroller = Gtk.ScrolledWindow()
        tab.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        tab.textview = Gtk.TextView()
        tab.textview.set_monospace(True)
        tab.textview.set_left_margin(8)
        tab.textview.set_right_margin(8)
        tab.textview.get_buffer().connect("changed", self._on_buffer_changed, tab)
        tab.scroller.add(tab.textview)
        tab.container.pack_start(tab.scroller, True, True, 0)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tab.label = Gtk.Label(label=self._tab_title(tab))
        header.pack_start(tab.label, True, True, 0)
        close = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.MENU)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.connect("clicked", lambda *_: self._close_specific_tab(tab))
        header.pack_start(close, False, False, 0)
        header.show_all()

        idx = self.notebook.append_page(tab.container, header)
        self.notebook.set_tab_reorderable(tab.container, True)
        self.tabs.append(tab)
        tab.container.show_all()
        self.notebook.set_current_page(idx)
        self._load_tab_content(tab)
        self._update_tabbar_visibility()
        return tab

    def _tab_title(self, tab):
        if tab.asset and tab.asset.name:
            t = tab.asset.name
        elif tab.asset and tab.asset.stem:
            t = naming.humanize(tab.asset.stem)
        else:
            t = "(empty)"
        if len(t) > 14:
            t = t[:12] + "\u2026"
        return ("*" + t) if tab.dirty else t

    def _current_tab(self):
        idx = self.notebook.get_current_page()
        if idx < 0:
            return None
        page = self.notebook.get_nth_page(idx)
        for tab in self.tabs:
            if tab.container is page:
                return tab
        return None

    def _load_tab_content(self, tab):
        """Fill a tab's editor buffer from its asset (or a placeholder)."""
        buf = tab.textview.get_buffer()
        if tab.asset is None:
            buf.set_text("")
            tab.textview.set_editable(False)
        else:
            self._suppress_dirty = True
            buf.set_text(tab.asset.raw_text)
            self._suppress_dirty = False
            tab.textview.set_editable(not self.read_only and not self.preview_on)
        tab.dirty = False
        self._render_tab(tab)
        if tab.label:
            tab.label.set_text(self._tab_title(tab))

    def _render_tab(self, tab):
        """Swap the tab body between plaintext editor and preview card."""
        # Remove any non-scroller child (a previous preview).
        for child in tab.container.get_children():
            if child is not tab.scroller:
                tab.container.remove(child)
        if self.preview_on and tab.asset is not None:
            tab.scroller.hide()
            # Sync structured fields from possibly-edited text first.
            self._sync_asset_from_buffer(tab)
            preview = build_preview(tab.asset, tab.workspace_disp)
            tab.container.pack_start(preview, True, True, 0)
            preview.show_all()
        else:
            tab.scroller.show()
            tab.textview.set_editable(
                tab.asset is not None and not self.read_only
            )

    def _sync_asset_from_buffer(self, tab):
        if tab.asset is None:
            return
        buf = tab.textview.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True)
        tab.asset.update_from_raw(text)

    _suppress_dirty = False

    def _on_buffer_changed(self, _buf, tab):
        if self._suppress_dirty:
            return
        if not tab.dirty:
            tab.dirty = True
            if tab.label:
                tab.label.set_text(self._tab_title(tab))

    def _close_specific_tab(self, tab):
        if tab not in self.tabs:
            return
        page_num = self.notebook.page_num(tab.container)
        if page_num >= 0:
            self.notebook.remove_page(page_num)
        self.tabs.remove(tab)
        if not self.tabs:
            self.new_tab()
        self._update_tabbar_visibility()

    def _update_tabbar_visibility(self):
        self.notebook.set_show_tabs(len(self.tabs) > 1)

    # ====================================================================
    # Selection handlers
    # ====================================================================
    def on_nav_selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        kind = model[it][NAV_KIND]
        folder_path = model[it][NAV_PATH]
        ws_root = model[it][NAV_WS_ROOT]
        self._fill_item_list(folder_path, ws_root, include_workspace_root=(
            kind == KIND_WORKSPACE))

    def _fill_item_list(self, folder_path, ws_root, include_workspace_root):
        self.item_store.clear()
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        node = ws.find_node(folder_path)
        if node is None:
            return
        for asset_path in node.asset_files:
            stem = os.path.splitext(os.path.basename(asset_path))[0]
            self.item_store.append(
                [naming.humanize(stem), asset_path, ws_root]
            )
        count = len(node.asset_files)
        self.set_status("%d asset%s in this folder"
                        % (count, "" if count == 1 else "s"))

    def on_filter_changed(self, _entry):
        self.item_filter.refilter()

    def on_item_selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        asset_path = model[it][ITEM_PATH]
        ws_root = model[it][ITEM_WS_ROOT]
        self._open_asset_in_current_tab(asset_path, ws_root)

    def on_item_activated(self, _view, _path, _col):
        # Double-click / Enter opens in a fresh tab.
        model, it = self.item_view.get_selection().get_selected()
        if it is None:
            return
        self._open_asset_in_new_tab(model[it][ITEM_PATH], model[it][ITEM_WS_ROOT])

    def _open_asset_in_current_tab(self, asset_path, ws_root):
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        tab = self._current_tab()
        if tab is None:
            tab = self.new_tab()
        try:
            tab.asset = ws.load_asset(asset_path)
        except Exception as exc:
            self.set_status("Could not open asset: %s" % exc)
            return
        tab.workspace_disp = ws.display_name
        self._load_tab_content(tab)
        self.set_status("Opened %s" % tab.asset.name)

    def _open_asset_in_new_tab(self, asset_path, ws_root):
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        try:
            asset = ws.load_asset(asset_path)
        except Exception as exc:
            self.set_status("Could not open asset: %s" % exc)
            return
        self.new_tab(asset=asset, workspace_disp=ws.display_name)

    def on_tab_switched(self, _nb, _page, _num):
        # Defer: page widget is set after this signal completes.
        GLib.idle_add(self._after_tab_switch)

    def _after_tab_switch(self):
        tab = self._current_tab()
        if tab:
            self._render_tab(tab)
        return False

    # ====================================================================
    # Toolbar / menu action handlers
    # ====================================================================
    def on_new_tab(self, *_):
        self.new_tab()

    def on_close_tab(self, *_):
        tab = self._current_tab()
        if tab:
            self._close_specific_tab(tab)

    def on_new_asset(self, *_):
        # Determine target folder from nav selection.
        model, it = self.nav_view.get_selection().get_selected()
        if it is None:
            self.set_status("Select a workspace or folder first.")
            return
        folder_path = model[it][NAV_PATH]
        ws_root = model[it][NAV_WS_ROOT]
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        name = self._prompt_text("New asset", "Asset name:", "new_asset")
        if not name:
            return
        new_path = ws.new_asset_path(folder_path, name)
        asset = Asset(path=None, workspace_root=ws_root)
        asset.name = naming.humanize(
            os.path.splitext(os.path.basename(new_path))[0]
        )
        try:
            asset.save(new_path)
        except Exception as exc:
            self.set_status("Could not create asset: %s" % exc)
            return
        ws.refresh()
        self.refresh_workspaces()
        self.new_tab(asset=ws.load_asset(new_path), workspace_disp=ws.display_name)
        self.set_status("Created %s" % os.path.basename(new_path))

    def on_save_asset(self, *_):
        tab = self._current_tab()
        if tab is None or tab.asset is None:
            self.set_status("Nothing to save in this tab.")
            return
        if self.read_only:
            self.set_status("Read-only mode is on \u2014 cannot save.")
            return
        if not self.preview_on:
            self._sync_asset_from_buffer(tab)
        try:
            tab.asset.save()
        except Exception as exc:
            self.set_status("Save failed: %s" % exc)
            return
        tab.dirty = False
        tab.label.set_text(self._tab_title(tab))
        self.set_status("Saved %s" % os.path.basename(tab.asset.path))

    def on_open_workspace(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Open workspace folder", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Open", Gtk.ResponseType.ACCEPT,
        )
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.open_workspace(dialog.get_filename())
        dialog.destroy()

    def on_close_workspace(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None:
            self.set_status("Select a workspace to close.")
            return
        ws_root = model[it][NAV_WS_ROOT]
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        self.workspaces.remove(ws)
        self.settings.note_closed(ws_root)
        self.settings.save()
        self.refresh_workspaces()
        self.item_store.clear()
        self.set_status("Closed workspace: %s" % ws.display_name)

    def on_new_folder(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None:
            self.set_status("Select a workspace or folder first.")
            return
        parent_path = model[it][NAV_PATH]
        ws_root = model[it][NAV_WS_ROOT]
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        name = self._prompt_text("New folder", "Folder name:", "new_folder")
        if not name:
            return
        try:
            ws.create_folder(parent_path, name)
        except Exception as exc:
            self.set_status("Could not create folder: %s" % exc)
            return
        self.refresh_workspaces()
        self.set_status("Created folder %s" % naming.slugify(name))

    def on_refresh(self, *_):
        self.refresh_workspaces()
        self.set_status("Workspaces refreshed.")

    def on_toggle_toolbar(self, item):
        self.settings["show_toolbar"] = item.get_active()
        self.toolbar.set_visible(item.get_active())
        self.settings.save()

    def on_toggle_statusbar(self, item):
        self.settings["show_statusbar"] = item.get_active()
        self.statusbar.set_visible(item.get_active())
        self.settings.save()

    def on_toggle_cardview(self, _btn):
        # Card view is a lightweight presentation toggle for the item list;
        # here it simply notes status (the list renderer stays text rows).
        on = self.tb_cardview.get_active()
        self.set_status("Card view %s" % ("on" if on else "off"))

    # --- read-only (kept in sync between toolbar + menu) -------------------
    def on_toolbar_readonly(self, btn):
        self._set_read_only(btn.get_active(), source="toolbar")

    def on_menu_readonly(self, item):
        self._set_read_only(item.get_active(), source="menu")

    def _set_read_only(self, value, source):
        self.read_only = value
        if source != "toolbar":
            self.tb_readonly.handler_block(self.tb_readonly_hid)
            self.tb_readonly.set_active(value)
            self.tb_readonly.handler_unblock(self.tb_readonly_hid)
        if source != "menu":
            self.mi_readonly.set_active(value)
        self.settings["read_only"] = value
        self.settings.save()
        for tab in self.tabs:
            tab.textview.set_editable(
                tab.asset is not None and not value and not self.preview_on
            )
        self._refresh_status()

    # --- preview (kept in sync between toolbar + menu) ---------------------
    def on_toolbar_preview(self, btn):
        self._set_preview(btn.get_active(), source="toolbar")

    def on_menu_preview(self, item):
        self._set_preview(item.get_active(), source="menu")

    def _set_preview(self, value, source):
        self.preview_on = value
        if source != "toolbar":
            self.tb_preview.handler_block(self.tb_preview_hid)
            self.tb_preview.set_active(value)
            self.tb_preview.handler_unblock(self.tb_preview_hid)
        if source != "menu":
            self.mi_preview.set_active(value)
        for tab in self.tabs:
            self._render_tab(tab)
        self._refresh_status()

    def on_about(self, *_):
        dlg = Gtk.AboutDialog(transient_for=self, modal=True)
        dlg.set_program_name(__app_name__)
        dlg.set_version(__version__)
        dlg.set_comments(
            "Track your tools, equipment, and materials across workspaces."
        )
        dlg.set_license_type(Gtk.License.MIT_X11)
        dlg.set_logo_icon_name("package-x-generic")
        dlg.run()
        dlg.destroy()

    # ====================================================================
    # Helpers
    # ====================================================================
    def _prompt_text(self, title, label_text, default=""):
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_OK", Gtk.ResponseType.OK,
        )
        box = dialog.get_content_area()
        box.set_spacing(6)
        box.set_border_width(10)
        box.pack_start(Gtk.Label(label=label_text, xalign=0.0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        result = dialog.run()
        text = entry.get_text().strip()
        dialog.destroy()
        return text if result == Gtk.ResponseType.OK else None

    def _rebuild_recent_menu(self):
        for child in self.recent_menu.get_children():
            self.recent_menu.remove(child)
        recents = self.settings["recent_workspaces"]
        if not recents:
            empty = Gtk.MenuItem.new_with_label("(none)")
            empty.set_sensitive(False)
            self.recent_menu.append(empty)
        else:
            for path in recents:
                item = Gtk.MenuItem.new_with_label(path)
                item.connect(
                    "activate",
                    lambda _i, p=path: self.open_workspace(p),
                )
                self.recent_menu.append(item)
        self.recent_menu.show_all()

    def _apply_view_settings(self):
        self.toolbar.set_visible(bool(self.settings["show_toolbar"]))
        self.statusbar.set_visible(bool(self.settings["show_statusbar"]))

    def set_status(self, text):
        self._last_status = text
        self._refresh_status()

    def _refresh_status(self):
        mode = "READ-ONLY" if self.read_only else "EDIT"
        preview = "  |  PREVIEW" if self.preview_on else ""
        msg = getattr(self, "_last_status", "Ready")
        self.statusbar.pop(self._status_ctx)
        self.statusbar.push(
            self._status_ctx,
            "%s    \u2014    Mode: %s%s" % (msg, mode, preview),
        )

    def on_destroy(self, *_):
        self.settings.save()
        Gtk.main_quit()
