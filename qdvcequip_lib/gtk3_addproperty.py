"""gtk3_addproperty.py — the "Add property" dialog (GTK3 view).

Lets the user add one of the catalogued asset properties (see
``property_catalog``) that the current asset doesn't already have. Layout:

  * Left  — a list of the missing properties.
  * Right — for the selected property, a short explanation of its purpose and
            an appropriate entry field: a genre dropdown for ``genre``, a date
            picker for ``purchased``, and a plain text entry for the rest.
  * Bottom — Cancel / Save.

The dialog is a pure view over the catalog and the Asset; it does not touch the
editor buffer itself. ``run_modal`` returns ``(spec, value)`` on Save (so the
caller can apply it via ``Asset.add_property``) or ``None`` on Cancel / when
there is nothing to add.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from . import genre as genre_mod
from . import property_catalog as catalog


class AddPropertyDialog(Gtk.Dialog):

    def __init__(self, parent, asset):
        super().__init__(title="Add property", transient_for=parent, modal=True)
        self.set_default_size(560, 340)
        self._asset = asset
        self._specs = catalog.missing_specs(asset)
        self._current = None      # selected PropertySpec
        self._field = None        # the active entry widget

        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        self._save_btn = self.add_button("_Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        content = self.get_content_area()
        content.set_border_width(8)
        content.set_spacing(8)

        if not self._specs:
            content.add(Gtk.Label(
                label="This asset already has every known property.",
                xalign=0.0))
            self._save_btn.set_sensitive(False)
            self.show_all()
            return

        # Two-column body: property list on the left, detail pane on the right.
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        body.set_hexpand(True)
        body.set_vexpand(True)
        content.add(body)

        # --- left: missing-property list ---
        left = Gtk.ScrolledWindow()
        left.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left.set_size_request(180, -1)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        for spec in self._specs:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=spec.label, xalign=0.0)
            lbl.set_margin_top(4)
            lbl.set_margin_bottom(4)
            lbl.set_margin_start(6)
            lbl.set_margin_end(6)
            row.add(lbl)
            row._spec = spec
            self._listbox.add(row)
        self._listbox.connect("row-selected", self._on_row_selected)
        left.add(self._listbox)
        body.pack_start(left, False, False, 0)

        # --- right: detail pane (description + field) ---
        self._detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._detail.set_hexpand(True)

        self._title_label = Gtk.Label(xalign=0.0)
        self._detail.pack_start(self._title_label, False, False, 0)

        self._desc_label = Gtk.Label(xalign=0.0)
        self._desc_label.set_line_wrap(True)
        self._desc_label.set_xalign(0.0)
        self._detail.pack_start(self._desc_label, False, False, 0)

        self._field_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   spacing=4)
        self._detail.pack_start(self._field_box, False, False, 0)

        body.pack_start(self._detail, True, True, 0)

        self.show_all()
        # Select the first property so the detail pane is never empty.
        self._listbox.select_row(self._listbox.get_row_at_index(0))

    # ------------------------------------------------------------------ #
    def _on_row_selected(self, _listbox, row):
        if row is None:
            return
        self._current = row._spec
        self._build_detail(row._spec)

    def _build_detail(self, spec):
        self._title_label.set_markup("<b>%s</b>" % _escape(spec.label))
        self._desc_label.set_text(spec.description)

        for child in self._field_box.get_children():
            self._field_box.remove(child)

        if spec.field == catalog.FIELD_GENRE:
            combo = Gtk.ComboBoxText()
            for g in genre_mod.all_genres():
                combo.append_text(g)   # verbatim, never humanized
            combo.set_active(0)
            self._field = combo
        elif spec.field == catalog.FIELD_DATE:
            cal = Gtk.Calendar()
            self._field = cal
        else:
            entry = Gtk.Entry()
            entry.set_activates_default(True)
            self._field = entry

        self._field_box.pack_start(self._field, False, False, 0)
        self._field_box.show_all()

    def _current_value(self):
        """Read the value from the active field as a string."""
        spec = self._current
        if spec is None or self._field is None:
            return ""
        if spec.field == catalog.FIELD_GENRE:
            return self._field.get_active_text() or ""
        if spec.field == catalog.FIELD_DATE:
            year, month, day = self._field.get_date()
            # Gtk.Calendar months are 0-based.
            return "%04d-%02d-%02d" % (year, month + 1, day)
        return self._field.get_text().strip()

    # ------------------------------------------------------------------ #
    def run_modal(self):
        """Show the dialog. Return (spec, value) on Save, else None.

        The dialog is destroyed before returning.
        """
        if not self._specs:
            self.run()
            self.destroy()
            return None
        result = None
        if self.run() == Gtk.ResponseType.OK and self._current is not None:
            result = (self._current, self._current_value())
        self.destroy()
        return result


def _escape(text):
    return (str(text).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))
