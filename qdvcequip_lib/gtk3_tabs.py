"""gtk3_tabs.py — the details-notebook tab lifecycle (GTK3 view).

A **mixin** combined into EquipWindow (see gtk3_window.py). It owns everything
about the pane-3 notebook of AssetTab objects: creating/closing tabs, loading
an asset's text into a tab, swapping a tab body between the plaintext editor
and the rendered preview card, per-tab editor styling (code font + line
spacing), and — on tab switch — reflecting the landed-on tab's read-only/preview
state back onto the toolbar/menu toggles.

Read-only and Preview are per-tab (like qdvc-markdown-notebook); the window
fields `self.read_only` / `self.preview_mode` are just mirrors of the active
tab that the status bar and gating read.

Relies on attributes/handlers defined across the window and its other mixins
(notebook, tabs, settings, on_tab_context_menu, _sync_toggle, btn_/mi_ toggles,
set_status/update_status).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402

from .gtk3_common import parse_font
from .gtk3_preview import build_preview
from .gtk3_editortab import AssetTab


class TabsMixin:
    """The pane-3 notebook: tab lifecycle, rendering, styling, switch sync."""

    # Guards the dirty flag while we programmatically fill a buffer.
    _suppress_dirty = False

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
        family, size = parse_font(self.settings.code_font)
        css = "textview, textview text { font-family: %s; font-size: %dpt; }" % (
            family, size)
        try:
            provider.load_from_data(css.encode("utf-8"))
        except Exception:
            pass

    def _apply_editor_style_all(self):
        for tab in self.tabs:
            self._apply_editor_style(tab)

    # ----- tab switch + toggle sync ----------------------------------------
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
