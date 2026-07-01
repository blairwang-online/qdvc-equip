"""gtk3_toolbar.py — GTK3 toolbar construction + styling for EquipWindow.

A **mixin** combined into EquipWindow in gtk3_window.py. GTK3-specific; relies
on handlers/attributes defined across the window and its other mixins.

The toolbar order is: New tab \u00b7 New asset \u00b7 Save asset \u2502 Card view \u2502
Read-only \u00b7 Preview. Card view and Preview reuse the exact theme icons from
qdvc-markdown-notebook (mail-attachment and document-page-setup) so the two
apps feel like siblings. The icon-text placement (beside vs below) follows the
toolbar_style setting, adjustable in Preferences.

GTK notes for non-GTK readers:
  * Gtk.Toolbar lays out a row of items; insert(item, -1) appends at the end.
  * A plain ToolButton fires "clicked"; a Gtk.ToggleToolButton stays pressed-in
    and fires "toggled", with get_active() giving its state.
  * set_is_important(True) keeps a button's label beside its icon in the
    BOTH_HORIZ style; connect(...) returns a handler id we keep for toggles we
    need to drive programmatically without re-firing the handler.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .settings import TOOLBAR_TEXT_BESIDE


class ToolbarMixin:
    """Toolbar construction + style for EquipWindow (see module docstring)."""

    def _build_toolbar(self):
        toolbar = Gtk.Toolbar()
        self.toolbar = toolbar
        toolbar.set_style(self._toolbar_style_enum())

        btn_new_tab = Gtk.ToolButton(icon_name="tab-new")
        btn_new_tab.set_label("New tab")
        btn_new_tab.set_tooltip_text("Open a new tab")
        btn_new_tab.set_is_important(True)
        btn_new_tab.connect("clicked", self.on_new_tab)
        toolbar.insert(btn_new_tab, -1)

        self.btn_new_asset = Gtk.ToolButton(icon_name="document-new")
        self.btn_new_asset.set_label("New asset")
        self.btn_new_asset.set_tooltip_text("Create a new asset")
        self.btn_new_asset.set_is_important(True)
        self.btn_new_asset.connect("clicked", self.on_new_asset)
        toolbar.insert(self.btn_new_asset, -1)

        self.btn_save = Gtk.ToolButton(icon_name="document-save")
        self.btn_save.set_label("Save asset")
        self.btn_save.set_tooltip_text("Save the current asset")
        self.btn_save.set_is_important(True)
        self.btn_save.connect("clicked", self.on_save_asset)
        toolbar.insert(self.btn_save, -1)

        self.btn_add_property = Gtk.ToolButton(icon_name="list-add")
        self.btn_add_property.set_label("Add property")
        self.btn_add_property.set_tooltip_text(
            "Add a known property to the current asset")
        self.btn_add_property.set_is_important(True)
        self.btn_add_property.connect("clicked", self.on_add_property)
        toolbar.insert(self.btn_add_property, -1)

        toolbar.insert(self._toolbar_separator(), -1)

        # Card view toggle: pane 2 shows each asset as a small multi-line card
        # (bold name + asset tag + location-notes snippet). Same icon as the
        # notebook's card-view button.
        self.btn_cardview = Gtk.ToggleToolButton()
        self.btn_cardview.set_icon_name("mail-attachment")
        self.btn_cardview.set_label("Card view")
        self.btn_cardview.set_tooltip_text("Show the item list as cards")
        self.btn_cardview.set_active(False)
        self.btn_cardview.set_is_important(True)
        self.btn_cardview.connect("toggled", self.on_toggle_card_view)
        toolbar.insert(self.btn_cardview, -1)

        toolbar.insert(self._toolbar_separator(), -1)

        # Read-only toggle. Pressed-in means read-only; applies across all tabs.
        # Disabled while Preview is on (preview is read-only by construction).
        self.btn_readonly = Gtk.ToggleToolButton()
        self.btn_readonly.set_icon_name("changes-prevent-symbolic")
        self.btn_readonly.set_label("Read-only")
        self.btn_readonly.set_tooltip_text(
            "Toggle read-only mode (applies to all tabs)")
        self.btn_readonly.set_active(self.read_only)
        self.btn_readonly.set_is_important(True)
        self._readonly_handler = self.btn_readonly.connect(
            "toggled", self.on_toggle_read_only)
        toolbar.insert(self.btn_readonly, -1)

        # Preview toggle: render the asset as a card instead of YAML. Same icon
        # as the notebook's preview button. Activating it disables Read-only.
        self.btn_preview = Gtk.ToggleToolButton()
        self.btn_preview.set_icon_name("document-page-setup")
        self.btn_preview.set_label("Preview")
        self.btn_preview.set_tooltip_text(
            "Render the asset as a card instead of YAML text")
        self.btn_preview.set_active(False)
        self.btn_preview.set_is_important(True)
        self.btn_preview.connect("toggled", self.on_toggle_preview)
        toolbar.insert(self.btn_preview, -1)

        return toolbar

    @staticmethod
    def _toolbar_separator():
        sep = Gtk.SeparatorToolItem()
        sep.set_draw(True)
        return sep

    def _toolbar_style_enum(self):
        # Map our stored preference ("below"/"beside") to GTK's toolbar style:
        # BOTH = label under the icon; BOTH_HORIZ = label beside the icon (only
        # for items flagged set_is_important).
        if self.settings.toolbar_style == TOOLBAR_TEXT_BESIDE:
            return Gtk.ToolbarStyle.BOTH_HORIZ
        return Gtk.ToolbarStyle.BOTH

    def _apply_toolbar_style(self):
        # Re-apply after the user changes it in Preferences.
        self.toolbar.set_style(self._toolbar_style_enum())
