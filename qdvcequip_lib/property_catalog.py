"""property_catalog.py — the catalog of known asset properties (GTK-free core).

The "Add property" dialog offers the user any property from the documented
sample asset that their file doesn't already have. This module is the single
source of truth for that catalog: for each property it records where it lives on
the Asset (a top-level attribute like ``genre`` / ``location_notes``, or a key
inside the ``asset_information`` mapping), a human explanation of its purpose,
and which kind of entry field the dialog should show.

Keeping this here (GTK-free) means the "which properties are missing" logic and
the catalog itself can be unit-tested without a display; the dialog in
``gtk3_addproperty`` is a thin view over it.
"""

from collections import OrderedDict

# Field-kind tags the dialog maps to concrete widgets.
FIELD_TEXT = "text"        # a single-line text entry
FIELD_GENRE = "genre"      # a dropdown of the built-in genres
FIELD_DATE = "date"        # a calendar / date picker

# Where a property is stored on the Asset.
LOC_TOPLEVEL = "toplevel"  # an Asset attribute (e.g. asset.genre)
LOC_INFO = "info"          # a key inside asset.info (asset_information)


class PropertySpec(object):
    """One catalogued property: key, storage location, help text, field kind."""

    def __init__(self, key, location, field, description):
        self.key = key
        self.location = location
        self.field = field
        self.description = description

    @property
    def label(self):
        """Human label for the property.

        `genre` is shown verbatim (never humanized); every other key is the
        snake_case key humanized ("asset_tag" -> "Asset Tag").
        """
        if self.key == "genre":
            return "genre"
        from . import naming
        return naming.humanize(self.key)


# The catalogued properties, in the order they appear in the sample asset.
# `name` is intentionally omitted: it is mandatory and always already present.
_SPECS = [
    PropertySpec(
        "genre", LOC_TOPLEVEL, FIELD_GENRE,
        "A coarse category for the asset (e.g. appliances, laptops). It sets "
        "the icon shown in the item list and lets you filter by genre in the "
        "navigation tree. Shown verbatim, never reworded."),
    PropertySpec(
        "location_notes", LOC_TOPLEVEL, FIELD_TEXT,
        "Free-text hints for physically finding the asset — landmarks, what to "
        "move aside, which drawer, and so on. The asset's location itself comes "
        "from the folders it is filed under, so this is just extra guidance."),
    PropertySpec(
        "asset_tag", LOC_INFO, FIELD_TEXT,
        "Your own inventory/asset tag — the identifier on the label you stuck "
        "on the item. Used to mark an asset as \u201ctagged\u201d in the "
        "navigation tree."),
    PropertySpec(
        "retailer", LOC_INFO, FIELD_TEXT,
        "Where the asset was bought (the shop or online store), handy for "
        "warranty claims and re-orders."),
    PropertySpec(
        "manufacturer", LOC_INFO, FIELD_TEXT,
        "The company that makes the asset (e.g. the brand), as distinct from "
        "the retailer that sold it."),
    PropertySpec(
        "model", LOC_INFO, FIELD_TEXT,
        "The manufacturer's model name or number identifying exactly which "
        "product this is."),
    PropertySpec(
        "serial_number", LOC_INFO, FIELD_TEXT,
        "The unit's unique serial number, usually printed on the device or its "
        "packaging — needed for support and warranty."),
    PropertySpec(
        "receipt_ref", LOC_INFO, FIELD_TEXT,
        "A reference to the purchase receipt or invoice (a number or filename), "
        "so you can find proof of purchase later."),
    PropertySpec(
        "purchased", LOC_INFO, FIELD_DATE,
        "The date the asset was bought (YYYY-MM-DD). The preview shows it as a "
        "friendly date plus the asset's age."),
    PropertySpec(
        "price", LOC_INFO, FIELD_TEXT,
        "What the asset cost, ideally with its currency (e.g. \u201c251.50 "
        "EUR\u201d), for insurance and depreciation records."),
]

# Lookup by key, preserving order.
CATALOG = OrderedDict((s.key, s) for s in _SPECS)


def all_specs():
    """Return the catalogued PropertySpec objects in sample order."""
    return list(_SPECS)


def spec_for(key):
    """Return the PropertySpec for *key*, or None if it isn't catalogued."""
    return CATALOG.get(key)


def asset_has_property(asset, spec):
    """True if *asset* already carries the property described by *spec*."""
    if spec.location == LOC_TOPLEVEL:
        return bool(getattr(asset, spec.key, ""))
    return spec.key in asset.info and bool(str(asset.info[spec.key]).strip())


def missing_specs(asset):
    """Return the catalogued specs *asset* does not already have (sample order).

    A None asset (an empty tab with nothing loaded) yields the full catalog.
    """
    if asset is None:
        return list(_SPECS)
    return [s for s in _SPECS if not asset_has_property(asset, s)]
