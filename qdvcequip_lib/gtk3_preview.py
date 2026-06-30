"""gtk3_preview.py — the asset Preview pane (GTK3 view).

The "Preview" toolbar toggle replaces the plaintext YAML editor with a rendered,
read-only card built from real GTK widgets (labels, sections, and per-row
``[copy]`` buttons). This is QDVC Equip's analogue of the notebook's markdown
preview, but instead of rich text it produces a structured equipment card:

    \u2615 Coffee Machine            <- large heading
    Location
    | Home \u2192 Kitchen \u2192 Pantry
    Location Notes
    | ...wrapped notes...
    Asset Information
    | Asset tag: SDR892314T          [copy]
    | Manufacturer: Coffee Machines  [copy]
    | ...

The breadcrumb's first crumb is the workspace name, followed by each humanized
folder the asset is nested in.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango  # noqa: E402


def build_preview(asset, workspace_display_name=""):
    """Return a Gtk.Widget rendering *asset* as a read-only card."""
    outer = Gtk.ScrolledWindow()
    outer.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_border_width(16)

    # --- heading: emoji + name in large text ------------------------------
    heading_text = asset.name or asset.stem or "Untitled asset"
    if asset.emoji:
        heading_text = "%s  %s" % (asset.emoji, heading_text)
    heading = Gtk.Label(xalign=0.0)
    heading.set_markup(
        '<span size="xx-large" weight="bold">%s</span>'
        % GLib_escape(heading_text)
    )
    heading.set_line_wrap(True)
    box.pack_start(heading, False, False, 0)

    # --- Location section --------------------------------------------------
    crumbs = []
    if workspace_display_name:
        crumbs.append(workspace_display_name)
    crumbs.extend(asset.location_parts())
    if crumbs:
        _add_section_title(box, "Location")
        breadcrumb = "  \u2192  ".join(crumbs)
        _add_quoted_line(box, breadcrumb)

    # --- Location notes ----------------------------------------------------
    if asset.location_notes.strip():
        _add_section_title(box, "Location Notes")
        _add_quoted_line(box, asset.location_notes.strip(), wrap=True)

    # --- Asset information (copyable rows) ---------------------------------
    if asset.info:
        _add_section_title(box, "Asset Information")
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(4)
        grid.set_margin_start(8)
        for row, (label, value) in enumerate(asset.info.items()):
            bar = Gtk.Label(label="|", xalign=0.0)
            bar.get_style_context().add_class("dim-label")
            grid.attach(bar, 0, row, 1, 1)

            text = Gtk.Label(xalign=0.0)
            text.set_markup(
                "<b>%s:</b> %s"
                % (GLib_escape(label), GLib_escape(value))
            )
            text.set_line_wrap(True)
            text.set_hexpand(True)
            grid.attach(text, 1, row, 1, 1)

            copy_btn = Gtk.Button(label="copy")
            copy_btn.set_relief(Gtk.ReliefStyle.NORMAL)
            copy_btn.set_tooltip_text("Copy \u201c%s\u201d to clipboard" % value)
            copy_btn.connect("clicked", _on_copy_clicked, value)
            grid.attach(copy_btn, 2, row, 1, 1)
        box.pack_start(grid, False, False, 0)

    # Empty-state hint.
    if not crumbs and not asset.location_notes.strip() and not asset.info:
        hint = Gtk.Label(xalign=0.0)
        hint.set_markup(
            '<span foreground="#888">This asset has no details yet. '
            "Switch off Preview to edit its YAML.</span>"
        )
        box.pack_start(hint, False, False, 8)

    outer.add(box)
    outer.show_all()
    return outer


# --------------------------------------------------------------------------
def _add_section_title(box, title):
    lbl = Gtk.Label(xalign=0.0)
    lbl.set_markup("<b>%s</b>" % GLib_escape(title))
    lbl.set_margin_top(10)
    box.pack_start(lbl, False, False, 0)


def _add_quoted_line(box, text, wrap=False):
    """A '|'-prefixed, indented block echoing the doc's visual style."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_margin_start(8)
    bar = Gtk.Label(label="|", xalign=0.0, yalign=0.0)
    bar.get_style_context().add_class("dim-label")
    row.pack_start(bar, False, False, 0)
    body = Gtk.Label(label=text, xalign=0.0)
    if wrap:
        body.set_line_wrap(True)
        body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    body.set_hexpand(True)
    row.pack_start(body, True, True, 0)
    box.pack_start(row, False, False, 0)


def _on_copy_clicked(_button, value):
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(value, -1)
    clipboard.store()


def GLib_escape(text):
    """Escape Pango markup special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
