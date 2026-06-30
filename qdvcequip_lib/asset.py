"""asset.py — the Asset data model and YAML (de)serialisation (GTK-free core).

An *asset* is a single tool, piece of equipment, or set of materials, stored as
one ``.yml`` file inside a workspace's folder tree. The folder path the file
sits in *is* its real-world location (kitchen → pantry, etc.), so location is
derived from the filesystem rather than stored in the YAML.

The YAML body holds the descriptive fields the Preview pane renders:

    name: Coffee Machine
    emoji: "\u2615"
    location_notes: |
      You might need to move aside the cartons of UHT milk which
      may be blocking your view of the coffee machine.
    info:
      Asset tag: SDR892314T
      Manufacturer: Coffee Machines Inc.
      Model: Cino Grande XL Gen. 2
      Serial number: 689D857D6

``info`` is an ordered mapping of arbitrary label → value pairs; each becomes a
row with a [copy] button in the Preview pane. Everything is optional — a brand
new asset is simply ``name`` derived from its filename.

This module degrades gracefully without PyYAML: it can still read and write a
small, predictable subset of YAML so the application runs on a bare install.
"""

import io
import os
from collections import OrderedDict

try:  # PyYAML is preferred when present.
    import yaml
    _HAVE_YAML = True
except Exception:  # pragma: no cover - exercised only on bare installs.
    yaml = None
    _HAVE_YAML = False

from . import naming


class Asset(object):
    """In-memory representation of one ``.yml`` asset file.

    Attributes:
        path:           absolute path to the .yml file (None if unsaved).
        workspace_root: absolute path to the owning workspace folder.
        name:           display name (defaults to humanized filename stem).
        emoji:          a short glyph shown before the name in Preview.
        location_notes: free text describing where/how to find it.
        info:           OrderedDict of label -> value asset-information rows.
    """

    def __init__(self, path=None, workspace_root=None):
        self.path = path
        self.workspace_root = workspace_root
        self.name = ""
        self.emoji = ""
        self.location_notes = ""
        self.info = OrderedDict()
        # Raw text last loaded/saved; lets the plaintext view round-trip
        # comments and ordering the structured parser might drop.
        self._raw_text = ""

    # ----- identity helpers ------------------------------------------------
    @property
    def stem(self):
        """Filename without the .yml extension, or '' if unsaved."""
        if not self.path:
            return ""
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def folder(self):
        """Absolute path of the directory the asset lives in."""
        return os.path.dirname(self.path) if self.path else None

    def location_parts(self):
        """Return the location as a list of humanized folder names.

        For ``<workspace>/kitchen/pantry/coffee_machine.yml`` relative to the
        workspace this yields ``["Kitchen", "Pantry"]``. The workspace name is
        not included here; callers prepend it for the breadcrumb.
        """
        if not self.path or not self.workspace_root:
            return []
        rel = os.path.relpath(os.path.dirname(self.path), self.workspace_root)
        if rel in (".", ""):
            return []
        return [naming.humanize(p) for p in rel.split(os.sep) if p]

    # ----- (de)serialisation ----------------------------------------------
    def to_dict(self):
        """Return an ordered dict suitable for YAML serialisation."""
        d = OrderedDict()
        d["name"] = self.name
        if self.emoji:
            d["emoji"] = self.emoji
        if self.location_notes:
            d["location_notes"] = self.location_notes
        if self.info:
            d["info"] = OrderedDict(self.info)
        return d

    def to_yaml(self):
        """Serialise this asset to a YAML string."""
        data = self.to_dict()
        if _HAVE_YAML:
            return yaml.safe_dump(
                _plain(data), default_flow_style=False, sort_keys=False,
                allow_unicode=True,
            )
        return _fallback_dump(data)

    @classmethod
    def from_yaml(cls, text, path=None, workspace_root=None):
        """Parse *text* (a YAML string) into an Asset."""
        asset = cls(path=path, workspace_root=workspace_root)
        asset._raw_text = text
        data = _safe_load(text) or {}
        if not isinstance(data, dict):
            data = {}
        asset.name = str(data.get("name") or "").strip()
        asset.emoji = str(data.get("emoji") or "").strip()
        asset.location_notes = str(data.get("location_notes") or "").rstrip()
        info = data.get("info") or {}
        if isinstance(info, dict):
            asset.info = OrderedDict(
                (str(k), "" if v is None else str(v)) for k, v in info.items()
            )
        # Sensible display fallback when name is omitted.
        if not asset.name and path:
            asset.name = naming.humanize(
                os.path.splitext(os.path.basename(path))[0]
            )
        return asset

    @classmethod
    def load(cls, path, workspace_root=None):
        """Read the asset at *path* from disk."""
        with io.open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        return cls.from_yaml(text, path=path, workspace_root=workspace_root)

    def save(self, path=None):
        """Write the asset to disk, returning the path written."""
        target = path or self.path
        if not target:
            raise ValueError("Asset has no path to save to")
        text = self.to_yaml()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with io.open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.path = target
        self._raw_text = text
        return target

    # ----- plaintext view round-trip --------------------------------------
    @property
    def raw_text(self):
        """The plaintext shown in the default (non-preview) editor view."""
        return self._raw_text or self.to_yaml()

    def update_from_raw(self, text):
        """Re-parse the structured fields from edited plaintext."""
        updated = Asset.from_yaml(
            text, path=self.path, workspace_root=self.workspace_root
        )
        self.name = updated.name
        self.emoji = updated.emoji
        self.location_notes = updated.location_notes
        self.info = updated.info
        self._raw_text = text


# --------------------------------------------------------------------------
# YAML helpers with graceful no-PyYAML fallback.
# --------------------------------------------------------------------------
def _plain(obj):
    """Recursively convert OrderedDicts to plain dicts for yaml.safe_dump."""
    if isinstance(obj, OrderedDict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def _safe_load(text):
    if _HAVE_YAML:
        try:
            return yaml.safe_load(text)
        except Exception:
            return {}
    return _fallback_load(text)


def _fallback_dump(data):
    """Very small YAML emitter for the subset this app writes.

    Handles top-level scalar keys, a multiline ``location_notes`` block, and a
    one-level-nested ``info`` mapping. Used only when PyYAML is unavailable.
    """
    lines = []
    for key, value in data.items():
        if key == "info" and isinstance(value, dict):
            lines.append("info:")
            for k, v in value.items():
                lines.append("  %s: %s" % (k, _scalar(v)))
        elif key == "location_notes" and isinstance(value, str) and "\n" in value:
            lines.append("location_notes: |")
            for ln in value.splitlines():
                lines.append("  " + ln)
        else:
            lines.append("%s: %s" % (key, _scalar(value)))
    return "\n".join(lines) + "\n"


def _scalar(v):
    if v is None:
        return ""
    s = str(v)
    # Quote when characters could confuse the naive reader below.
    if s == "" or s[0] in "#&*!|>%@`\"'" or ":" in s or s.strip() != s:
        return '"%s"' % s.replace('"', '\\"')
    return s


def _fallback_load(text):
    """Mirror of _fallback_dump for bare installs. Best-effort only."""
    data = OrderedDict()
    info = OrderedDict()
    lines = text.splitlines()
    i = 0
    in_info = False
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line.startswith("  ") and in_info:
            k, _, v = line.strip().partition(":")
            info[k.strip()] = _unscalar(v.strip())
            i += 1
            continue
        in_info = False
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "info":
            in_info = True
            i += 1
            continue
        if val == "|":
            block = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i][2:] if lines[i].startswith("  ") else "")
                i += 1
            data[key] = "\n".join(block).rstrip()
            continue
        data[key] = _unscalar(val)
        i += 1
    if info:
        data["info"] = info
    return data


def _unscalar(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1].replace('\\"', '"')
    return s
