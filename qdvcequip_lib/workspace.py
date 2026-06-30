"""workspace.py — workspace & nested folder-tree model (GTK-free core).

A *workspace* is a top-level folder (e.g. ``~/qdvc-equip/home``) holding an
arbitrarily nested tree of subfolders. Every ``.yml`` file in that tree is an
asset; the folders it nests under describe where the asset is stored.

Because the application can open several workspaces at once, the navigation
tree shows one ``Subfolders``-style root per open workspace, each expanding the
full nested hierarchy (unlike the single-level notebook this is modelled on).

This module walks the filesystem into ``FolderNode`` trees and enforces the
"no two folders or assets share a name within a workspace" rule used to keep
names unambiguous (sony_headphones_1 / _2 ...).

GTK-free: imports nothing from PyGObject.
"""

import os

from . import naming
from .asset import Asset

ASSET_EXT = ".yml"


class FolderNode(object):
    """A single folder within a workspace tree.

    Attributes:
        path:       absolute path to this folder.
        name:       basename of the folder ('' for the workspace root).
        children:   list of child FolderNode, sorted by name.
        asset_files: list of absolute .yml paths directly inside this folder.
    """

    def __init__(self, path, name):
        self.path = path
        self.name = name
        self.children = []
        self.asset_files = []

    @property
    def display_name(self):
        return naming.humanize(self.name) if self.name else ""

    def iter_descendant_assets(self):
        """Yield every asset file path in this folder and below it."""
        for f in self.asset_files:
            yield f
        for child in self.children:
            for f in child.iter_descendant_assets():
                yield f


class Workspace(object):
    """An open workspace rooted at a directory on disk."""

    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.root_node = None
        self.refresh()

    @property
    def name(self):
        return os.path.basename(self.root.rstrip(os.sep))

    @property
    def display_name(self):
        return naming.humanize(self.name)

    # ----- scanning --------------------------------------------------------
    def refresh(self):
        """Rebuild the folder tree from disk."""
        self.root_node = self._scan(self.root, name="")
        return self.root_node

    def _scan(self, path, name):
        node = FolderNode(path, name)
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            return node
        for entry in entries:
            if entry.startswith("."):
                continue
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                node.children.append(self._scan(full, entry))
            elif entry.lower().endswith(ASSET_EXT):
                node.asset_files.append(full)
        node.children.sort(key=lambda c: c.name)
        node.asset_files.sort()
        return node

    # ----- queries ---------------------------------------------------------
    def all_asset_files(self):
        """Every asset path anywhere in the workspace."""
        return list(self.root_node.iter_descendant_assets())

    def all_names(self):
        """Set of every folder name and asset stem in the workspace.

        Used to enforce workspace-wide name uniqueness when creating or
        renaming things.
        """
        names = set()

        def walk(node):
            for child in node.children:
                names.add(child.name)
                walk(child)
            for f in node.asset_files:
                names.add(os.path.splitext(os.path.basename(f))[0])

        walk(self.root_node)
        return names

    def load_asset(self, path):
        """Load a single asset, tagged with this workspace as its root."""
        return Asset.load(path, workspace_root=self.root)

    def find_node(self, folder_path):
        """Return the FolderNode whose .path matches *folder_path*, or None."""
        target = os.path.abspath(folder_path)

        def walk(node):
            if os.path.abspath(node.path) == target:
                return node
            for child in node.children:
                found = walk(child)
                if found:
                    return found
            return None

        return walk(self.root_node)

    # ----- mutations --------------------------------------------------------
    def new_asset_path(self, folder_path, desired_name):
        """Compute a free, convention-following path for a new asset.

        Honours the workspace-wide uniqueness rule by suffixing a number when
        the slug is already taken anywhere in the workspace.
        """
        stem = naming.unique_name(desired_name, self.all_names())
        return os.path.join(folder_path, stem + ASSET_EXT)

    def create_folder(self, parent_path, desired_name):
        """Create a uniquely-named subfolder, returning its path."""
        name = naming.unique_name(desired_name, self.all_names())
        path = os.path.join(parent_path, name)
        os.makedirs(path, exist_ok=False)
        self.refresh()
        return path
