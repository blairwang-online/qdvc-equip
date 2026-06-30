"""gtk3_window.py — the main application window (GTK3 view/controller).

Assembles the GNOME2-era layout and wires user actions to the GTK-free core.
Heavy construction lives in sibling mixins (gtk3_menubar.MenuBarMixin,
gtk3_toolbar.ToolbarMixin, gtk3_contextmenu.ContextMenuMixin); each AssetTab
(gtk3_editortab) owns its editor view, label, and per-tab state. This file
focuses on layout, the three panes, the notebook of tabs, and action handlers.

Layout: menubar, toolbar, three horizontal panes (navigation tree, items,
item details) in nested Gtk.Paned, and a status bar with a bold mode label
followed by a Gtk.Statusbar.

Multi-workspace navigation tree (pane 1): an "All Assets" row at the very top
(every asset in every open workspace), then one expandable root per workspace
rendering its full nested folder hierarchy. Selecting All Assets, a workspace,
or a folder fills the items pane (pane 2). Selecting an asset opens it in the
active tab (pane 3); double-click / Enter opens it in a new tab; right-click
raises the context menu.

Per-tab modes: Read-only and Preview are tracked per tab (like
qdvc-markdown-notebook). The toolbar/menu toggles act on the active tab, and
switching tabs reflects that tab's state back onto the toggles. Activating
Preview disables the Read-only toggle (preview is read-only by construction).
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
from .gtk3_menubar import MenuBarMixin
from .gtk3_toolbar import ToolbarMixin
from .gtk3_contextmenu import ContextMenuMixin
from .gtk3_preferences import PreferencesDialog
from .gtk3_editortab import AssetTab

# Navigation tree column indices.
NAV_LABEL, NAV_KIND, NAV_PATH, NAV_WS_ROOT = range(4)
KIND_ALL = "all_assets"
KIND_WORKSPACE = "workspace"
KIND_FOLDER = "folder"

# Item list column indices: label, path, ws_root, tag (card line 2),
# notes snippet (card line 3).
ITEM_LABEL, ITEM_PATH, ITEM_WS_ROOT, ITEM_TAG, ITEM_SNIPPET = range(5)


def _xml_escape(text):
    return (str(text).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _parse_font(font_desc):
    """Split a Pango font string like 'monospace 11' into (family, size_pt)."""
    parts = str(font_desc).split()
    size = 11
    if parts and parts[-1].isdigit():
        size = int(parts[-1])
        parts = parts[:-1]
    family = " ".join(parts) or "monospace"
    return family, size


class EquipWindow(MenuBarMixin, ToolbarMixin, ContextMenuMixin, Gtk.Window):
    """Top-level QDVC Equip window."""

    def __init__(self, workspace_paths=None):
        super().__init__(title=__app_name__)
        self.set_default_size(1100, 680)

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
        self.connect("destroy", self.on_destroy)

    # ====================================================================
    # UI construction
    # ====================================================================
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        root.pack_start(self._build_menubar(), False, False, 0)
        root.pack_start(self._build_toolbar(), False, False, 0)

        self.outer_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.inner_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.outer_paned.pack1(self._build_nav_pane(), resize=False, shrink=False)
        self.inner_paned.pack1(self._build_item_pane(), resize=True, shrink=False)
        self.inner_paned.pack2(self._build_details_pane(), resize=True, shrink=False)
        self.outer_paned.pack2(self.inner_paned, resize=True, shrink=False)
        self.outer_paned.set_position(260)
        self.inner_paned.set_position(280)
        root.pack_start(self.outer_paned, True, True, 0)

        root.pack_start(self._build_statusbar(), False, False, 0)
        self.update_status()

    # ----- status bar -------------------------------------------------------
    def _build_statusbar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.statusbar_box = box
        self.mode_label = Gtk.Label()
        self.mode_label.set_margin_start(6)
        self.mode_label.set_margin_end(6)
        box.pack_start(self.mode_label, False, False, 0)
        self.statusbar = Gtk.Statusbar()
        self._status_ctx = self.statusbar.get_context_id("main")
        box.pack_start(self.statusbar, True, True, 0)
        return box

    # ----- pane 1: navigation tree -----------------------------------------
    def _build_nav_pane(self):
        frame = Gtk.Frame()
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
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
        self._add_all_assets_row()
        return frame

    def _add_all_assets_row(self):
        # The "All Assets" virtual node sits at the very top (mirrors the
        # notebook's "All Notes").
        self.nav_store.append(
            None, ["All Assets", KIND_ALL, "", ""])

    def _nav_icon_func(self, _col, cell, model, it, _data):
        kind = model[it][NAV_KIND]
        cell.set_property("icon-name", {
            KIND_ALL: "emblem-documents",
            KIND_WORKSPACE: "drive-harddisk",
        }.get(kind, "folder"))

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
        # label, path, ws_root, tag, snippet
        self.item_store = Gtk.ListStore(str, str, str, str, str)
        self.item_filter = self.item_store.filter_new()
        self.item_filter.set_visible_func(self._item_visible_func)
        self.item_view = Gtk.TreeView(model=self.item_filter)
        self.item_view.set_headers_visible(False)

        col = Gtk.TreeViewColumn("Asset")
        icon = Gtk.CellRendererPixbuf()
        icon.set_property("icon-name", "package-x-generic")
        col.pack_start(icon, False)
        self._item_text_renderer = Gtk.CellRendererText()
        self._item_text_renderer.set_property(
            "ellipsize", Pango.EllipsizeMode.END)
        col.pack_start(self._item_text_renderer, True)
        col.set_cell_data_func(self._item_text_renderer, self._item_cell_data)
        self.item_view.append_column(col)

        self.item_view.get_selection().connect("changed", self.on_item_selected)
        self.item_view.connect("row-activated", self.on_item_activated)
        # Right-click context menu (handled in ContextMenuMixin).
        self.item_view.connect("button-press-event", self.on_items_button_press)
        sw.add(self.item_view)
        box.pack_start(sw, True, True, 0)
        frame.add(box)
        return frame

    def _item_visible_func(self, model, it, _data):
        term = self.search_entry.get_text().strip().lower()
        if not term:
            return True
        hay = " ".join([
            model[it][ITEM_LABEL] or "",
            model[it][ITEM_TAG] or "",
            model[it][ITEM_SNIPPET] or "",
        ]).lower()
        return term in hay

    def _item_cell_data(self, _col, cell, store, it, _data):
        title = _xml_escape(store[it][ITEM_LABEL])
        if not self.card_view:
            cell.set_property("ypad", 0)
            cell.set_property("markup", title)
            return
        tag = _xml_escape(store[it][ITEM_TAG])
        snippet = _xml_escape(store[it][ITEM_SNIPPET])
        sub = ""
        if tag:
            sub += "\n<i><span size='small'>%s</span></i>" % tag
        if snippet:
            sub += "\n<i><span size='small'>%s</span></i>" % snippet
        cell.set_property("ypad", 2)
        cell.set_property("markup", "<b>%s</b>%s" % (title, sub))

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
            None, [ws.display_name, KIND_WORKSPACE, ws.root, ws.root])
        self._populate_folder_children(ws_iter, ws.root_node, ws.root)
        self.nav_view.expand_row(self.nav_store.get_path(ws_iter), False)

    def _populate_folder_children(self, parent_iter, node, ws_root):
        for child in node.children:
            child_iter = self.nav_store.append(
                parent_iter,
                [child.display_name, KIND_FOLDER, child.path, ws_root])
            self._populate_folder_children(child_iter, child, ws_root)

    def _workspace_for_root(self, ws_root):
        for ws in self.workspaces:
            if ws.root == ws_root:
                return ws
        return None

    def refresh_workspaces(self):
        self.nav_store.clear()
        self._add_all_assets_row()
        for ws in self.workspaces:
            ws.refresh()
            self._add_workspace_to_nav(ws)

    # ====================================================================
    # Tabs (pane 3)
    # ====================================================================
    def new_tab(self, asset=None, workspace_disp=""):
        tab = AssetTab(
            on_close=self._close_specific_tab,
            on_context_menu=self.on_tab_context_menu,
            on_buffer_changed=self._on_buffer_changed,
            read_only=self.read_only,
        )
        tab.asset = asset
        tab.workspace_disp = workspace_disp
        self._apply_editor_style(tab)

        idx = self.notebook.append_page(tab.container, tab.tab_label)
        self.notebook.set_tab_reorderable(tab.container, True)
        self.tabs.append(tab)
        tab.container.show_all()
        self.notebook.set_current_page(idx)
        self._load_tab_content(tab)
        self._update_tabbar_visibility()
        return tab

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
        buf = tab.textview.get_buffer()
        self._suppress_dirty = True
        buf.set_text(tab.asset.raw_text if tab.asset is not None else "")
        self._suppress_dirty = False
        tab.dirty = False
        tab.refresh_title()
        self._render_tab(tab)
        self.update_status()

    def _render_tab(self, tab):
        """Swap a tab body between the editor and the preview card, honouring
        the tab's own preview/read-only state."""
        for child in tab.container.get_children():
            if child is not tab.scroller:
                tab.container.remove(child)
        if tab.preview and tab.asset is not None:
            tab.scroller.hide()
            self._sync_asset_from_buffer(tab)
            preview = build_preview(tab.asset, tab.workspace_disp)
            tab.container.pack_start(preview, True, True, 0)
            preview.show_all()
        else:
            tab.scroller.show()
            tab.textview.set_editable(
                tab.asset is not None and not tab.read_only)
        tab.refresh_status_icons()

    def _sync_asset_from_buffer(self, tab):
        if tab.asset is None:
            return
        tab.asset.update_from_raw(tab.get_content())

    _suppress_dirty = False

    def _on_buffer_changed(self, _buf, tab):
        if self._suppress_dirty:
            return
        if not tab.dirty:
            tab.dirty = True
            tab.refresh_title()
            self.update_status()

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
        self.update_status()

    def _update_tabbar_visibility(self):
        self.notebook.set_show_tabs(len(self.tabs) > 1)

    # ----- editor styling (code font + line spacing) ----------------------
    def _apply_editor_style(self, tab):
        spacing = self.settings.editor_line_spacing
        tab.textview.set_pixels_above_lines(spacing)
        tab.textview.set_pixels_below_lines(spacing)
        provider = tab._css_provider
        if provider is None:
            provider = Gtk.CssProvider()
            tab._css_provider = provider
            tab.textview.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        family, size = _parse_font(self.settings.code_font)
        css = "textview, textview text { font-family: %s; font-size: %dpt; }" % (
            family, size)
        try:
            provider.load_from_data(css.encode("utf-8"))
        except Exception:
            pass

    def _apply_editor_style_all(self):
        for tab in self.tabs:
            self._apply_editor_style(tab)

    # ====================================================================
    # Selection handlers
    # ====================================================================
    def on_nav_selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        kind = model[it][NAV_KIND]
        if kind == KIND_ALL:
            self._fill_item_list_all()
            return
        self._fill_item_list(model[it][NAV_PATH], model[it][NAV_WS_ROOT])

    def _append_item_row(self, ws, asset_path, ws_root):
        stem = os.path.splitext(os.path.basename(asset_path))[0]
        tag, snippet = "", ""
        try:
            a = ws.load_asset(asset_path)
            tag = a.asset_tag()
            snippet = a.notes_snippet()
        except Exception:
            pass
        self.item_store.append(
            [naming.humanize(stem), asset_path, ws_root, tag, snippet])

    def _fill_item_list(self, folder_path, ws_root):
        self.item_store.clear()
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        node = ws.find_node(folder_path)
        if node is None:
            return
        for asset_path in node.asset_files:
            self._append_item_row(ws, asset_path, ws_root)
        count = len(node.asset_files)
        self.set_status("%d asset%s in this folder"
                        % (count, "" if count == 1 else "s"))

    def _fill_item_list_all(self):
        self.item_store.clear()
        total = 0
        for ws in self.workspaces:
            for asset_path in ws.all_asset_files():
                self._append_item_row(ws, asset_path, ws.root)
                total += 1
        self.set_status("%d asset%s across all workspaces"
                        % (total, "" if total == 1 else "s"))

    def on_filter_changed(self, _entry):
        self.item_filter.refilter()

    def on_item_selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        self._open_asset_in_current_tab(
            model[it][ITEM_PATH], model[it][ITEM_WS_ROOT])

    def on_item_activated(self, _view, _path, _col):
        model, it = self.item_view.get_selection().get_selected()
        if it is None:
            return
        self._open_asset_in_new_tab(model[it][ITEM_PATH], model[it][ITEM_WS_ROOT])

    def _open_asset_in_current_tab(self, asset_path, ws_root):
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        tab = self._current_tab() or self.new_tab()
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
        GLib.idle_add(self._after_tab_switch)

    def _after_tab_switch(self):
        tab = self._current_tab()
        if tab:
            self._sync_toggles_to_tab(tab)
            self._render_tab(tab)
            self.update_status()
        return False

    def _sync_toggles_to_tab(self, tab):
        """Reflect the active tab's per-tab read-only/preview onto the toolbar
        + menu toggles, and mirror them onto the window fields the status bar
        reads. Guarded so setting the widgets doesn't re-fire the handlers."""
        self.read_only = tab.read_only
        self.preview_mode = tab.preview
        self._sync_toggle(self.btn_readonly, self.mi_readonly, self.read_only)
        self._sync_toggle(self.btn_preview, self.mi_preview, self.preview_mode)
        self.btn_readonly.set_sensitive(not self.preview_mode)
        self.mi_readonly.set_sensitive(not self.preview_mode)

    # ====================================================================
    # Action handlers
    # ====================================================================
    def on_new_tab(self, *_):
        self.new_tab()

    def on_close_tab(self, *_):
        tab = self._current_tab()
        if tab:
            self._close_specific_tab(tab)

    def on_quit(self, *_):
        self.close()

    def on_new_asset(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None or model[it][NAV_KIND] in (KIND_ALL,):
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
            os.path.splitext(os.path.basename(new_path))[0])
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
        if tab.read_only:
            self.set_status("Read-only mode is on \u2014 cannot save.")
            return
        if not tab.preview:
            self._sync_asset_from_buffer(tab)
        try:
            tab.asset.save()
        except Exception as exc:
            self.set_status("Save failed: %s" % exc)
            return
        tab.dirty = False
        tab.refresh_title()
        self.set_status("Saved %s" % os.path.basename(tab.asset.path))

    def on_open_workspace(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Open workspace folder", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                           "_Open", Gtk.ResponseType.ACCEPT)
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
            self.set_status("Select a workspace to close.")
            return
        self.workspaces.remove(ws)
        self.settings.note_closed(ws_root)
        self.settings.save()
        self.refresh_workspaces()
        self.item_store.clear()
        self.set_status("Closed workspace: %s" % ws.display_name)

    def on_new_folder(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None or model[it][NAV_KIND] == KIND_ALL:
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

    def on_preferences(self, *_):
        dlg = PreferencesDialog(self, self.settings, self._apply_preferences)
        dlg.run_modal()

    def _apply_preferences(self):
        self._apply_toolbar_style()
        self._apply_editor_style_all()

    def on_toggle_toolbar(self, item):
        self.settings["show_toolbar"] = item.get_active()
        self.toolbar.set_visible(item.get_active())
        self.settings.save()

    def on_toggle_statusbar(self, item):
        self.settings["show_statusbar"] = item.get_active()
        self.statusbar_box.set_visible(item.get_active())
        self.settings.save()

    # ----- toggle sync helper (toolbar <-> menu) ---------------------------
    def _sync_toggle(self, button, menu_item, active):
        self._syncing_view_toggles = True
        try:
            button.set_active(active)
            menu_item.set_active(active)
        finally:
            self._syncing_view_toggles = False

    # ----- card view (app-wide) --------------------------------------------
    def _set_card_view(self, value):
        self.card_view = bool(value)
        self._sync_toggle(self.btn_cardview, self.mi_cardview, self.card_view)
        self.item_view.get_column(0).queue_resize()
        self.item_view.queue_draw()
        self.set_status("Card view %s" % ("on" if self.card_view else "off"))

    def on_toggle_card_view(self, button):
        if self._syncing_view_toggles:
            return
        self._set_card_view(button.get_active())

    def on_menu_toggle_card_view(self, item):
        if self._syncing_view_toggles:
            return
        self._set_card_view(item.get_active())

    # ----- read-only (per active tab) --------------------------------------
    def _set_read_only(self, value):
        tab = self._current_tab()
        self.read_only = bool(value)
        # Remember the latest choice as the default for new tabs.
        self.settings["read_only"] = self.read_only
        self.settings.save()
        self._sync_toggle(self.btn_readonly, self.mi_readonly, self.read_only)
        if tab is not None:
            tab.read_only = self.read_only
            tab.textview.set_editable(
                tab.asset is not None and not tab.read_only and not tab.preview)
            tab.refresh_status_icons()
        self.update_status()

    def on_toggle_read_only(self, button):
        if self._syncing_view_toggles:
            return
        self._set_read_only(button.get_active())

    def on_menu_toggle_read_only(self, item):
        if self._syncing_view_toggles:
            return
        self._set_read_only(item.get_active())

    # ----- preview (per active tab) ----------------------------------------
    def _set_preview(self, value):
        tab = self._current_tab()
        self.preview_mode = bool(value)
        self._sync_toggle(self.btn_preview, self.mi_preview, self.preview_mode)
        # Preview is read-only by construction → lock the Read-only toggle.
        self.btn_readonly.set_sensitive(not self.preview_mode)
        self.mi_readonly.set_sensitive(not self.preview_mode)
        if tab is not None:
            tab.preview = self.preview_mode
            self._render_tab(tab)
        self.update_status()

    def on_toggle_preview(self, button):
        if self._syncing_view_toggles:
            return
        self._set_preview(button.get_active())

    def on_menu_toggle_preview(self, item):
        if self._syncing_view_toggles:
            return
        self._set_preview(item.get_active())

    def on_about(self, *_):
        dlg = Gtk.AboutDialog(transient_for=self, modal=True)
        dlg.set_program_name(__app_name__)
        dlg.set_version(__version__)
        dlg.set_comments(
            "Track your tools, equipment, and materials across workspaces.")
        dlg.set_license_type(Gtk.License.MIT_X11)
        dlg.set_logo_icon_name("package-x-generic")
        dlg.run()
        dlg.destroy()

    # ====================================================================
    # Helpers
    # ====================================================================
    def _prompt_text(self, title, label_text, default=""):
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                           "_OK", Gtk.ResponseType.OK)
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
                    "activate", lambda _i, p=path: self.open_workspace(p))
                self.recent_menu.append(item)
        self.recent_menu.show_all()

    def _apply_view_settings(self):
        self.toolbar.set_visible(bool(self.settings["show_toolbar"]))
        self.statusbar_box.set_visible(bool(self.settings["show_statusbar"]))

    def set_status(self, text):
        self._last_status = text
        self.update_status()

    def update_status(self):
        # Bold mode label reflects the ACTIVE tab; preview overrides read-only.
        if self.preview_mode:
            self.mode_label.set_markup("<b>PREVIEW</b>")
        elif self.read_only:
            self.mode_label.set_markup("<b>READ-ONLY</b>")
        else:
            self.mode_label.set_markup("<b>EDIT</b>")

        msg = self._last_status
        tab = self._current_tab()
        if tab and tab.dirty:
            msg += "  *"
        if len(self.tabs) > 1:
            idx = self.notebook.get_current_page() + 1
            msg += "    \u2014    Tab %d of %d" % (idx, len(self.tabs))
        self.statusbar.pop(self._status_ctx)
        self.statusbar.push(self._status_ctx, msg)

    def on_destroy(self, *_):
        self.settings.save()
        Gtk.main_quit()
