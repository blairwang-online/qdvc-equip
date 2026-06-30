"""settings.py — persisted user settings and recent workspaces (GTK-free core).

Settings live in a plain, git-trackable YAML file under the XDG config dir
(``~/.config/qdvc-equip/config.yml`` by default). The app runs fine without
PyYAML — in that case settings simply aren't persisted between runs.

Stored keys:
    open_workspaces: list of absolute workspace paths to reopen on launch.
    recent_workspaces: most-recently-opened workspace paths (capped).
    show_toolbar / show_statusbar: View-menu toggles.
    read_only: whether the app starts in read-only mode.
    code_font: Pango font description for the YAML/plaintext editor.
    editor_line_spacing: extra pixels of inter-line spacing in the editor.
    toolbar_style: "beside" or "below" — toolbar icon text placement.

The font / spacing / toolbar-style keys back the Edit -> Preferences dialog
(see gtk3_preferences.py). They are defined here, in the GTK-free core, so the
bounds and defaults can be validated and unit-tested without a display.
"""

import io
import os

try:
    import yaml
    _HAVE_YAML = True
except Exception:  # pragma: no cover
    yaml = None
    _HAVE_YAML = False

from . import __app_id__

_MAX_RECENT = 10

# --- Preferences-backed constants -----------------------------------------
DEFAULT_CODE_FONT = "monospace 11"

DEFAULT_EDITOR_LINE_SPACING = 0
MIN_LINE_SPACING = 0
MAX_LINE_SPACING = 40

TOOLBAR_TEXT_BESIDE = "beside"
TOOLBAR_TEXT_BELOW = "below"
DEFAULT_TOOLBAR_STYLE = TOOLBAR_TEXT_BELOW

_DEFAULTS = {
    "open_workspaces": [],
    "recent_workspaces": [],
    "show_toolbar": True,
    "show_statusbar": True,
    "read_only": True,
    "code_font": DEFAULT_CODE_FONT,
    "editor_line_spacing": DEFAULT_EDITOR_LINE_SPACING,
    "toolbar_style": DEFAULT_TOOLBAR_STYLE,
}


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, __app_id__)


def config_path():
    return os.path.join(config_dir(), "config.yml")


def _clamp_spacing(value, fallback):
    try:
        return max(MIN_LINE_SPACING, min(MAX_LINE_SPACING, int(value)))
    except (TypeError, ValueError):
        return fallback


class Settings(object):
    """Load/save a small dict of user settings."""

    def __init__(self, data=None):
        self._data = dict(_DEFAULTS)
        if data:
            self._data.update(data)
        # Coerce the typed/bounded keys.
        self._data["editor_line_spacing"] = _clamp_spacing(
            self._data.get("editor_line_spacing"), DEFAULT_EDITOR_LINE_SPACING
        )
        if self._data.get("toolbar_style") not in (
            TOOLBAR_TEXT_BESIDE, TOOLBAR_TEXT_BELOW
        ):
            self._data["toolbar_style"] = DEFAULT_TOOLBAR_STYLE

    # dict-ish access
    def __getitem__(self, key):
        return self._data.get(key, _DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    # ----- typed convenience properties + setters -------------------------
    @property
    def code_font(self):
        return self._data["code_font"]

    def set_code_font(self, value):
        if isinstance(value, str) and value.strip():
            self._data["code_font"] = value

    @property
    def editor_line_spacing(self):
        return self._data["editor_line_spacing"]

    def set_editor_line_spacing(self, value):
        self._data["editor_line_spacing"] = _clamp_spacing(
            value, self._data["editor_line_spacing"]
        )

    @property
    def toolbar_style(self):
        return self._data["toolbar_style"]

    def set_toolbar_style(self, value):
        if value in (TOOLBAR_TEXT_BESIDE, TOOLBAR_TEXT_BELOW):
            self._data["toolbar_style"] = value

    # ----- recent / open workspace bookkeeping ----------------------------
    def note_opened(self, path):
        """Record *path* as opened: add to open + bump in recent list."""
        path = os.path.abspath(os.path.expanduser(path))
        opens = [p for p in self._data["open_workspaces"] if p != path]
        opens.append(path)
        self._data["open_workspaces"] = opens
        recent = [p for p in self._data["recent_workspaces"] if p != path]
        recent.insert(0, path)
        self._data["recent_workspaces"] = recent[:_MAX_RECENT]

    def note_closed(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        self._data["open_workspaces"] = [
            p for p in self._data["open_workspaces"] if p != path
        ]

    # ----- persistence -----------------------------------------------------
    @classmethod
    def load(cls):
        path = config_path()
        if _HAVE_YAML and os.path.exists(path):
            try:
                with io.open(path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
                if isinstance(data, dict):
                    return cls(data)
            except Exception:
                pass
        return cls()

    def save(self):
        if not _HAVE_YAML:
            return False
        try:
            os.makedirs(config_dir(), exist_ok=True)
            with io.open(config_path(), "w", encoding="utf-8") as fh:
                yaml.safe_dump(
                    self._data, fh, default_flow_style=False, sort_keys=True,
                    allow_unicode=True,
                )
            return True
        except Exception:
            return False
