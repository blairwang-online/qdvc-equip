"""gtk3_panes.py — the three panes + status bar construction (GTK3 view).

A **mixin** combined into EquipWindow (see gtk3_window.py). It builds the
GNOME2-era layout — menubar/toolbar (from their own mixins), then three
horizontal panes in nested Gtk.Paned, then a status bar — and owns the cell
rendering for the navigation tree (pane 1) and the item list (pane 2),
including the genre-icon logic shared by both.

GTK notes for non-GTK readers:
  * A cell-data-func runs per row to set a renderer's properties from the
    model; that's how one column paints different icons/markup per row.
  * Gtk.TreeModelFilter wraps a store with a visible-func for live search.
  * Pixbufs for custom genre icons are cached by (path, mtime) so refiltering
    and redraws don't re-decode files.

Relies on handlers/attributes defined across the window and its other mixins
(e.g. on_nav_selected, on_item_selected, on_items_button_press, settings,
card_view, set_status/update_status).
"""

import io
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GdkPixbuf  # noqa: E402

from . import genre as genre_mod
from .gtk3_common import (
    NAV_LABEL, NAV_KIND, NAV_PATH,
    KIND_ALL, KIND_WORKSPACE,
    KIND_TAGS_ROOT, KIND_TAGGED, KIND_UNTAGGED,
    KIND_GENRE_ROOT, KIND_GENRE, KIND_WORKSPACES_ROOT,
    NO_GENRE_SENTINEL,
    ITEM_LABEL, ITEM_PATH, ITEM_TAG, ITEM_SNIPPET, ITEM_GENRE,
    xml_escape,
)


class PanesMixin:
    """Layout, the three panes, status bar, and pane-1/2 cell rendering."""

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
        self._build_static_nav_rows()
        return frame

    def _build_static_nav_rows(self):
        """Append the fixed top-level nav rows in order.

        All Assets, then the Asset Tags group (Tagged / Not Tagged), the Genres
        group (each built-in genre plus a trailing "(no genre)"), and finally
        the Workspaces group that all open workspaces nest under. Returns after
        recording iters for the group parents so workspaces can be added later.
        """
        # All Assets — the virtual "everything" node (mirrors "All Notes").
        self.nav_store.append(None, ["All Assets", KIND_ALL, "", ""])

        # Asset Tags group.
        tags_iter = self.nav_store.append(
            None, ["Asset Tags", KIND_TAGS_ROOT, "", ""])
        self.nav_store.append(tags_iter, ["Tagged", KIND_TAGGED, "", ""])
        self.nav_store.append(tags_iter, ["Not Tagged", KIND_UNTAGGED, "", ""])

        # Genres group — one row per built-in genre, verbatim (never humanized),
        # then a trailing "(no genre)" filter row.
        genre_iter = self.nav_store.append(
            None, ["Genres", KIND_GENRE_ROOT, "", ""])
        for g in genre_mod.all_genres():
            self.nav_store.append(genre_iter, [g, KIND_GENRE, g, ""])
        self.nav_store.append(
            genre_iter, ["(no genre)", KIND_GENRE, NO_GENRE_SENTINEL, ""])

        # Workspaces group — open workspaces are nested under this parent.
        self._workspaces_iter = self.nav_store.append(
            None, ["Workspaces", KIND_WORKSPACES_ROOT, "", ""])

    def _nav_icon_func(self, _col, cell, model, it, _data):
        kind = model[it][NAV_KIND]
        if kind == KIND_GENRE:
            # A genre row shows its (custom or built-in) icon; "(no genre)"
            # uses a neutral icon.
            val = model[it][NAV_PATH]
            if val == NO_GENRE_SENTINEL:
                cell.set_property("icon-name", "edit-clear")
                cell.set_property("pixbuf", None)
                return
            self._apply_genre_icon(cell, val)
            return
        cell.set_property("pixbuf", None)
        cell.set_property("icon-name", {
            KIND_ALL: "emblem-documents",
            KIND_TAGS_ROOT: "emblem-symbolic-link",
            KIND_TAGGED: "emblem-default",
            KIND_UNTAGGED: "important",
            KIND_GENRE_ROOT: "emblem-photos",
            KIND_WORKSPACES_ROOT: "emblem-generic",
            KIND_WORKSPACE: "applications-other",
        }.get(kind, "folder"))

    def _apply_genre_icon(self, cell, genre_value):
        """Set *cell* to *genre_value*'s icon: custom image if set, else stock.

        A custom icon (an image file chosen in Preferences) is loaded and
        scaled to a small pixbuf; the built-in freedesktop icon is applied by
        name. Unknown genres get the generic package icon so rows never blank
        out. Pixbufs are cached by (path, mtime).
        """
        custom = self.settings.genre_icon(genre_value)
        if custom:
            pb = self._custom_icon_pixbuf(custom)
            if pb is not None:
                cell.set_property("pixbuf", pb)
                return
        cell.set_property("pixbuf", None)
        name = genre_mod.icon_name(genre_value) or "package-x-generic"
        cell.set_property("icon-name", name)

    def _custom_icon_pixbuf(self, path, size=16):
        """Return a scaled GdkPixbuf for *path*, cached by (path, mtime).

        Returns None if the file is missing or can't be decoded, so callers
        fall back to the stock icon.
        """
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        cache = getattr(self, "_icon_pixbuf_cache", None)
        if cache is None:
            cache = self._icon_pixbuf_cache = {}
        key = (path, size)
        cached = cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
        except Exception:
            pb = None
        cache[key] = (mtime, pb)
        return pb

    def _invalidate_icon_caches(self):
        """Drop the custom-icon pixbuf cache and redraw both icon-bearing views.

        Called after Preferences changes a custom genre icon, so the nav tree
        and items pane repaint with the new (or reset) icons.
        """
        self._icon_pixbuf_cache = {}
        if getattr(self, "nav_view", None) is not None:
            self.nav_view.queue_draw()
        if getattr(self, "item_view", None) is not None:
            self.item_view.queue_draw()

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
        # label, path, ws_root, tag, snippet, genre
        self.item_store = Gtk.ListStore(str, str, str, str, str, str)
        self.item_filter = self.item_store.filter_new()
        self.item_filter.set_visible_func(self._item_visible_func)
        self.item_view = Gtk.TreeView(model=self.item_filter)
        self.item_view.set_headers_visible(False)

        col = Gtk.TreeViewColumn("Asset")
        self._item_icon_renderer = Gtk.CellRendererPixbuf()
        col.pack_start(self._item_icon_renderer, False)
        col.set_cell_data_func(self._item_icon_renderer, self._item_icon_data)
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
        if term in hay:
            return True
        # Fall back to matching the asset's full file contents (like
        # qdvc-markdown-notebook), so a search finds text that isn't shown in
        # the pane-2 list. Reads are cached per path+mtime to keep refiltering
        # on each keystroke cheap; an unreadable file simply doesn't match here.
        path = model[it][ITEM_PATH] or ""
        return term in self._asset_contents_lower(path)

    def _asset_contents_lower(self, path):
        """Lowercased full file contents for `path`, cached by (path, mtime)."""
        if not path:
            return ""
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return ""
        cache = getattr(self, "_content_cache", None)
        if cache is None:
            cache = self._content_cache = {}
        cached = cache.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read().lower()
        except OSError:
            text = ""
        cache[path] = (mtime, text)
        return text

    def _item_icon_data(self, _col, cell, store, it, _data):
        """Paint each item row's icon from its genre (custom or built-in).

        A genreless asset (or one whose genre isn't a built-in) shows the
        generic package icon, matching the previous fixed behavior.
        """
        g = store[it][ITEM_GENRE] or ""
        if g and genre_mod.is_genre(g):
            self._apply_genre_icon(cell, g)
        else:
            cell.set_property("pixbuf", None)
            cell.set_property("icon-name", "package-x-generic")

    def _item_cell_data(self, _col, cell, store, it, _data):
        title = xml_escape(store[it][ITEM_LABEL])
        if not self.card_view:
            cell.set_property("ypad", 0)
            cell.set_property("markup", title)
            return
        tag = xml_escape(store[it][ITEM_TAG])
        snippet = xml_escape(store[it][ITEM_SNIPPET])
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
