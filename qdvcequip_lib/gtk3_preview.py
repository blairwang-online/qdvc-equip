"""gtk3_preview.py — the asset Preview pane (GTK3 view).

The "Preview" toggle replaces the plaintext YAML editor with a rendered,
read-only card built from real GTK widgets (labels, sections, and per-row
``[copy]`` buttons). This is QDVC Equip's analogue of the notebook's markdown
preview, but instead of rich text it produces a structured equipment card:

    [48px genre icon]  Coffee Machine   <- heading: genre icon + name
    Genre                        <- only shown when a genre is set
        appliances               (verbatim — never humanized)
    Location            [navigate]
        Home --> Kitchen --> Pantry
    Location Notes               <- only shown when notes are present
        ...wrapped notes...
    Asset Information
        Asset Tag:     SDR892314T              [copy]
        Manufacturer:  Coffee Machines Inc.    [copy]
        Model:         Cino Grande XL Gen. 2   [copy]
        Serial Number: 689D857D6               [copy]

The heading shows the 48x48 icon for the asset's genre (or the generic package
icon when it has none), resolved by the caller and passed in as *icon_pixbuf* —
the emoji is no longer rendered. Next to the Location title a "navigate" button
(when *on_navigate* is supplied) reveals the asset in the nav tree / item list.

Asset-information labels are humanized from their snake_case YAML keys. Their
*values* are column-aligned with one another, following the GNOME2/MATE/GTK
convention — achieved with a Gtk.Grid (label in column 0, value in column 1,
copy button in column 2) plus a SizeGroup so the label column is exactly as
wide as its widest label. Each [copy] button (icon ``edit-copy``) puts that
row's value on the clipboard. The ``purchased`` row is special-cased: its ISO
date is shown as a friendly date plus the asset's age (e.g. ``Wed 01 Jul 2026
(52d)``) while the copy button still copies the raw value (see
``qdvcequip_lib.dates``).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango  # noqa: E402

from . import naming
from . import dates
from . import genre as genre_mod

# How far section bodies are indented from the left edge (the rendered spec
# shows the body indented under each section title).
_BODY_INDENT = 24


def build_preview(asset, workspace_display_name="", icon_pixbuf=None,
                  on_navigate=None):
    """Return a Gtk.Widget rendering *asset* as a read-only card.

    *icon_pixbuf* is the 48x48 genre icon shown in the heading (the caller
    resolves it; None falls back to no image). *on_navigate*, if given, is a
    zero-argument callback wired to a "navigate" button beside the Location
    title that reveals the asset in the nav tree / item list.
    """
    outer = Gtk.ScrolledWindow()
    outer.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_border_width(16)

    # --- heading: 48x48 genre icon + name in large text -------------------
    heading_text = asset.name or asset.stem or "Untitled asset"
    heading_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    if icon_pixbuf is not None:
        img = Gtk.Image.new_from_pixbuf(icon_pixbuf)
        img.set_valign(Gtk.Align.CENTER)
        heading_row.pack_start(img, False, False, 0)
    heading = Gtk.Label(xalign=0.0)
    heading.set_markup(
        '<span size="xx-large" weight="bold">%s</span>'
        % _escape(heading_text))
    heading.set_line_wrap(True)
    heading.set_valign(Gtk.Align.CENTER)
    heading_row.pack_start(heading, False, False, 0)
    box.pack_start(heading_row, False, False, 0)

    # --- Genre (optional; shown verbatim, never humanized) ----------------
    if asset.genre:
        _add_section_title(box, "Genre")
        _add_indented_line(box, asset.genre)

    # --- Location section --------------------------------------------------
    crumbs = []
    if workspace_display_name:
        crumbs.append(workspace_display_name)
    crumbs.extend(asset.location_parts())
    if crumbs:
        _add_location_title(box, "Location", on_navigate)
        breadcrumb = "  \u2192  ".join(crumbs)
        _add_indented_line(box, breadcrumb)

    # --- Location notes (optional) ----------------------------------------
    if asset.location_notes.strip():
        _add_section_title(box, "Location Notes")
        _add_indented_line(box, asset.location_notes.strip(), wrap=True)

    # --- Asset information (value-aligned, copyable rows) -----------------
    # Build (label, display_value, copy_value) triples from the raw snake_case
    # keys so we can special-case `purchased` (shown as a friendly date plus
    # the asset's age) while still copying the underlying ISO value.
    rows = []
    for key, value in asset.info.items():
        label = naming.humanize(key)
        display = value
        copy_value = value
        if key.strip().lower() == "purchased":
            formatted = dates.format_purchased(value)
            if formatted:
                display = formatted
        rows.append((label, display, copy_value))
    if rows:
        _add_section_title(box, "Asset Information")

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(4)
        grid.set_margin_start(_BODY_INDENT)
        # A horizontal SizeGroup forces every label cell to share the width of
        # the widest one, so the value column lines up across all rows.
        label_group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        for r, (label, value, copy_value) in enumerate(rows):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_markup("<b>%s:</b>" % _escape(label))
            label_group.add_widget(lbl)
            grid.attach(lbl, 0, r, 1, 1)

            val = Gtk.Label(label=value, xalign=0.0)
            val.set_line_wrap(True)
            val.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            val.set_selectable(True)
            val.set_hexpand(True)
            grid.attach(val, 1, r, 1, 1)

            copy_btn = Gtk.Button()
            copy_btn.set_image(Gtk.Image.new_from_icon_name(
                "edit-copy", Gtk.IconSize.BUTTON))
            copy_btn.set_label("copy")
            copy_btn.set_always_show_image(True)
            copy_btn.set_tooltip_text(
                "Copy \u201c%s\u201d to clipboard" % copy_value)
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.connect("clicked", _on_copy_clicked, copy_value)
            grid.attach(copy_btn, 2, r, 1, 1)

        box.pack_start(grid, False, False, 0)

    # Empty-state hint.
    if not crumbs and not asset.location_notes.strip() and not rows:
        hint = Gtk.Label(xalign=0.0)
        hint.set_markup(
            '<span foreground="#888">This asset has no details yet. '
            "Switch off Preview to edit its YAML.</span>")
        box.pack_start(hint, False, False, 8)

    outer.add(box)
    outer.show_all()
    return outer


# --------------------------------------------------------------------------
def _add_section_title(box, title):
    lbl = Gtk.Label(xalign=0.0)
    lbl.set_markup("<b>%s</b>" % _escape(title))
    lbl.set_margin_top(10)
    box.pack_start(lbl, False, False, 0)


def _add_location_title(box, title, on_navigate):
    """Section title with an optional "navigate" button to its right."""
    if on_navigate is None:
        _add_section_title(box, title)
        return
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_margin_top(10)
    lbl = Gtk.Label(xalign=0.0)
    lbl.set_markup("<b>%s</b>" % _escape(title))
    lbl.set_valign(Gtk.Align.CENTER)
    row.pack_start(lbl, False, False, 0)
    btn = Gtk.Button()
    btn.set_image(Gtk.Image.new_from_icon_name(
        "folder-open", Gtk.IconSize.BUTTON))
    btn.set_label("navigate")
    btn.set_always_show_image(True)
    btn.set_tooltip_text("Reveal this asset in the navigation tree")
    btn.set_valign(Gtk.Align.CENTER)
    btn.connect("clicked", lambda _b: on_navigate())
    row.pack_start(btn, False, False, 0)
    box.pack_start(row, False, False, 0)


def _add_indented_line(box, text, wrap=False):
    """An indented body line under a section title."""
    lbl = Gtk.Label(label=text, xalign=0.0)
    lbl.set_margin_start(_BODY_INDENT)
    if wrap:
        lbl.set_line_wrap(True)
        lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    box.pack_start(lbl, False, False, 0)


def _on_copy_clicked(_button, value):
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(value, -1)
    clipboard.store()


def _escape(text):
    """Escape Pango markup special characters."""
    return (str(text).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))
