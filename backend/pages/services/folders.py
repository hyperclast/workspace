"""
Folder validation and helper services.
"""

import re

from pages.models import Folder

MAX_FOLDER_NAME_LENGTH = 255
MAX_FOLDER_DEPTH = 10
MAX_FOLDERS_PER_PROJECT = 500

# Control characters: U+0000-U+001F and U+007F
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
FORBIDDEN_CHARS_PATTERN = re.compile(r"[/\\]")


def validate_folder_name(name):
    """
    Validate and clean a folder name.

    Returns the cleaned name or raises ValueError with (message, code).
    """
    if name is None:
        raise ValueError("Folder name cannot be empty.", "name_required")

    name = name.strip()

    if not name:
        raise ValueError("Folder name cannot be empty.", "name_required")

    if len(name) > MAX_FOLDER_NAME_LENGTH:
        raise ValueError(f"Folder name cannot exceed {MAX_FOLDER_NAME_LENGTH} characters.", "name_too_long")

    if FORBIDDEN_CHARS_PATTERN.search(name) or CONTROL_CHARS_PATTERN.search(name):
        raise ValueError("Folder name contains forbidden characters.", "invalid_name")

    return name


def build_parent_map(project):
    """
    Fetch all folders for a project and build a parent map.

    Returns:
        dict: {folder_id: parent_id} for all folders in the project
    """
    folders = Folder.objects.filter(project=project).values_list("id", "parent_id")
    return {folder_id: parent_id for folder_id, parent_id in folders}


def would_create_cycle(folder_id, new_parent_id, parent_map):
    """Return True if setting folder's parent to new_parent_id creates a cycle."""
    current = new_parent_id
    while current is not None:
        if current == folder_id:
            return True
        current = parent_map.get(current)
    return False


def get_depth(folder_id, parent_map):
    """Return 1-based depth of a folder."""
    depth = 1
    current = folder_id
    while parent_map.get(current) is not None:
        depth += 1
        current = parent_map[current]
    return depth


def check_depth_limit(folder_id, parent_map, max_depth=MAX_FOLDER_DEPTH):
    """Check if a folder exceeds the maximum nesting depth."""
    depth = get_depth(folder_id, parent_map)
    if depth > max_depth:
        raise ValueError(f"Folder nesting cannot exceed {max_depth} levels.", "depth_limit_exceeded")
    return depth


def get_subtree_max_depth(folder_id, parent_map):
    """
    Get the maximum depth of any descendant relative to folder_id.

    Used when moving a folder to check if the subtree would exceed depth limits
    at its new position.
    """
    # Build children map
    children_map = {}
    for fid, pid in parent_map.items():
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    # BFS to find max depth in subtree
    max_depth = 0
    queue = [(folder_id, 0)]
    while queue:
        current, depth = queue.pop(0)
        max_depth = max(max_depth, depth)
        for child_id in children_map.get(current, []):
            queue.append((child_id, depth + 1))

    return max_depth
