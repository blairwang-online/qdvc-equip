"""gtk3_preferences.py — the Edit -> Preferences dialog (GTK3 view).

The *view* for the settings model (qdvcequip_lib.settings): a tabbed dialog
that edits what settings.py stores, in the GNOME2 / MATE idiom.

  * Fonts     — Code font (the YAML/plaintext editor font) and Editor line
                spacing (extra pixels between lines).
  * Interface — Toolbar icon text placement (beside vs below the icon).
  * Genres    — Set a custom image as the icon for any built-in genre, see an
                overview of which genres have custom icons, and reset them all.

Changes preview live in the app while the dialog is open. Save persists to
disk; Cancel (or closing the window) restores the values that were in effect
when the dialog opened and re-applies them, discarding the live preview.

This is the QDVC Equip subset of the notebook's richer preferences — only the
settings this app actually has are exposed.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf  # noqa: E402

from . import genre as genre_mod
from .settings import (
    TOOLBAR_TEXT_BESIDE,
    TOOLBAR_TEXT_BELOW,
    MIN_LINE_SPACING,
    MAX_LINE_SPACING,
)


class PreferencesDialog(Gtk.Dialog):

    def __init__(self, parent, settings, on_apply):
        super().__init__(title="Preferences", transient_for=parent, modal=True)
        self.settings = settings
        self._on_apply = on_apply

        # Snapshot the values in effect when the dialog opened, so Cancel can
        # restore them (and revert the live preview).
        self._original = {
            "code_font": settings.code_font,
            "editor_line_spacing": settings.editor_line_spacing,
            "toolbar_style": settings.toolbar_style,
            "genre_icons": settings.genre_icons,
        }

        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("_Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(460, -1)

        notebook = Gtk.Notebook()
        notebook.set_border_width(8)
        notebook.append_page(self._build_fonts_tab(), Gtk.Label(label="Fonts"))
        notebook.append_page(self._build_interface_tab(),
                             Gtk.Label(label="Interface"))
        notebook.append_page(self._build_genres_tab(),
                             Gtk.Label(label="Genres"))

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_border_width(8)
        content.add(notebook)
        self.show_all()

    # -------------------------------------------------------- Fonts tab -- #
    def _build_fonts_tab(self):
        # A Gtk.Grid (rows x columns): column 0 labels, column 1 controls.
        # A Gtk.FontButton opens the system font picker and fires "font-set";
        # a Gtk.SpinButton is a bounded number entry firing "value-changed".
        grid = Gtk.Grid(row_spacing=8, column_spacing=12)
        grid.set_border_width(12)

        row = 0
        grid.attach(self._label("Code font"), 0, row, 1, 1)
        self.code_font_btn = Gtk.FontButton()
        self.code_font_btn.set_font(self.settings.code_font)
        self.code_font_btn.set_hexpand(True)
        self.code_font_btn.connect("font-set", self._on_code_font_set)
        grid.attach(self.code_font_btn, 1, row, 1, 1)

        row += 1
        grid.attach(self._label("Editor line spacing"), 0, row, 1, 1)
        self.editor_spacing_spin = Gtk.SpinButton.new_with_range(
            MIN_LINE_SPACING, MAX_LINE_SPACING, 1)
        self.editor_spacing_spin.set_value(self.settings.editor_line_spacing)
        self.editor_spacing_spin.set_halign(Gtk.Align.START)
        self.editor_spacing_spin.connect(
            "value-changed", self._on_editor_spacing_changed)
        grid.attach(self.editor_spacing_spin, 1, row, 1, 1)

        return grid

    def _on_code_font_set(self, btn):
        self.settings.set_code_font(btn.get_font())
        self._on_apply()

    def _on_editor_spacing_changed(self, spin):
        self.settings.set_editor_line_spacing(spin.get_value_as_int())
        self._on_apply()

    # ---------------------------------------------------- Interface tab -- #
    def _build_interface_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(12)

        tb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tb_box.add(Gtk.Label(label="Toolbar icon text placement", xalign=0.0))

        # RadioButtons in one group so exactly one is active.
        self._radio_below = Gtk.RadioButton.new_with_label_from_widget(
            None, "Text below icons")
        self._radio_beside = Gtk.RadioButton.new_with_label_from_widget(
            self._radio_below, "Text beside icons")

        if self.settings.toolbar_style == TOOLBAR_TEXT_BESIDE:
            self._radio_beside.set_active(True)
        else:
            self._radio_below.set_active(True)

        self._radio_below.connect("toggled", self._on_toolbar_style_toggled)
        self._radio_beside.connect("toggled", self._on_toolbar_style_toggled)
        tb_box.add(self._radio_below)
        tb_box.add(self._radio_beside)
        box.add(tb_box)

        return box

    def _on_toolbar_style_toggled(self, _btn):
        style = (TOOLBAR_TEXT_BESIDE if self._radio_beside.get_active()
                 else TOOLBAR_TEXT_BELOW)
        self.settings.set_toolbar_style(style)
        self._on_apply()

    # ------------------------------------------------------- Genres tab -- #
    def _build_genres_tab(self):
        """Custom-icon management for the built-in genres.

        Two sections: (1) pick a genre and set/clear a custom image as its icon;
        (2) an overview of which genres currently have custom icons, plus a
        reset-all button (confirmed before it acts).
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(12)

        # --- Section 1: set custom icon for a genre ---
        box.add(Gtk.Label(
            label="Set custom icon for genre", xalign=0.0))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._genre_combo = Gtk.ComboBoxText()
        for g in genre_mod.all_genres():
            # Genre names are shown verbatim — never humanized.
            self._genre_combo.append_text(g)
        self._genre_combo.set_active(0)
        self._genre_combo.connect("changed", self._on_genre_selected)
        row.pack_start(self._genre_combo, False, False, 0)

        # A small preview of the selected genre's current icon.
        self._genre_icon_image = Gtk.Image()
        row.pack_start(self._genre_icon_image, False, False, 0)
        box.add(row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        set_btn = Gtk.Button(label="Set custom image\u2026")
        set_btn.connect("clicked", self._on_set_genre_icon)
        btn_row.pack_start(set_btn, False, False, 0)
        self._genre_clear_btn = Gtk.Button(label="Use built-in icon")
        self._genre_clear_btn.connect("clicked", self._on_clear_genre_icon)
        btn_row.pack_start(self._genre_clear_btn, False, False, 0)
        box.add(btn_row)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # --- Section 2: overview + reset all ---
        box.add(Gtk.Label(label="Overview", xalign=0.0))
        self._genre_overview = Gtk.Label(xalign=0.0)
        self._genre_overview.set_line_wrap(True)
        box.add(self._genre_overview)

        reset_btn = Gtk.Button(label="Reset all custom icons")
        reset_btn.set_halign(Gtk.Align.START)
        reset_btn.connect("clicked", self._on_reset_all_genre_icons)
        box.add(reset_btn)

        self._refresh_genre_tab()
        return box

    def _selected_genre(self):
        return self._genre_combo.get_active_text() or ""

    def _refresh_genre_tab(self):
        """Sync the icon preview, clear-button state, and overview text."""
        g = self._selected_genre()
        custom = self.settings.genre_icon(g)
        # Preview: custom image if set, else the built-in named icon.
        if custom:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(custom, 24, 24)
                self._genre_icon_image.set_from_pixbuf(pb)
            except Exception:
                self._genre_icon_image.set_from_icon_name(
                    "image-missing", Gtk.IconSize.LARGE_TOOLBAR)
        else:
            self._genre_icon_image.set_from_icon_name(
                genre_mod.icon_name(g) or "package-x-generic",
                Gtk.IconSize.LARGE_TOOLBAR)
        self._genre_clear_btn.set_sensitive(bool(custom))

        # Overview line.
        names = self.settings.genres_with_custom_icons()
        if names:
            self._genre_overview.set_text(
                "The current genre have custom icons set: "
                + "; ".join(names))
        else:
            self._genre_overview.set_text("No custom icons set.")

    def _on_genre_selected(self, _combo):
        self._refresh_genre_tab()

    def _on_set_genre_icon(self, _btn):
        g = self._selected_genre()
        if not g:
            return
        chooser = Gtk.FileChooserDialog(
            title="Choose an icon image for \u201c%s\u201d" % g,
            transient_for=self, action=Gtk.FileChooserAction.OPEN)
        chooser.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        chooser.add_button("_Open", Gtk.ResponseType.OK)
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Images")
        img_filter.add_mime_type("image/*")
        chooser.add_filter(img_filter)
        if chooser.run() == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            if path:
                self.settings.set_genre_icon(g, path)
                self._on_apply()
                self._refresh_genre_tab()
        chooser.destroy()

    def _on_clear_genre_icon(self, _btn):
        g = self._selected_genre()
        if not g:
            return
        self.settings.set_genre_icon(g, "")
        self._on_apply()
        self._refresh_genre_tab()

    def _on_reset_all_genre_icons(self, _btn):
        if not self.settings.genres_with_custom_icons():
            return
        confirm = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Reset all custom genre icons?")
        confirm.format_secondary_text(
            "Every genre will go back to its built-in icon. This can't be "
            "undone from here.")
        response = confirm.run()
        confirm.destroy()
        if response == Gtk.ResponseType.OK:
            self.settings.clear_genre_icons()
            self._on_apply()
            self._refresh_genre_tab()

    # ------------------------------------------------------- run/commit -- #
    def run_modal(self):
        """Show the dialog; on Save persist, on Cancel/close revert + re-apply.

        run() blocks until the user responds and returns the response code.
        The dialog is destroyed before returning either way.
        """
        response = self.run()
        if response == Gtk.ResponseType.OK:
            self.settings.save()
        else:
            o = self._original
            self.settings.set_code_font(o["code_font"])
            self.settings.set_editor_line_spacing(o["editor_line_spacing"])
            self.settings.set_toolbar_style(o["toolbar_style"])
            self.settings.set_genre_icons(o["genre_icons"])
            self._on_apply()
        self.destroy()

    # ----------------------------------------------------------- helper -- #
    @staticmethod
    def _label(text):
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(0.0)
        return lbl
