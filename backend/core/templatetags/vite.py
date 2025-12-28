import json
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

_manifest_cache = None


def _load_manifest():
    global _manifest_cache
    if _manifest_cache is not None and not settings.DEBUG:
        return _manifest_cache

    manifest_path = Path(settings.BASE_DIR).parent / "frontend" / "dist" / ".vite" / "manifest.json"
    if not manifest_path.exists():
        manifest_path = Path(settings.STATIC_ROOT) / "core" / "spa" / ".vite" / "manifest.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            _manifest_cache = json.load(f)
    else:
        _manifest_cache = {}

    return _manifest_cache


@register.simple_tag
def vite_asset(entry):
    manifest = _load_manifest()
    if not manifest:
        return f"/static/core/spa/assets/js/{entry}"

    entry_data = manifest.get(entry) or manifest.get(f"src/{entry}")
    if not entry_data:
        return f"/static/core/spa/assets/js/{entry}"

    return f"/static/core/spa/{entry_data['file']}"


@register.simple_tag
def vite_css(entry):
    manifest = _load_manifest()
    if not manifest:
        return '<link rel="stylesheet" href="/static/core/spa/assets/css/style.css">'

    tags = []

    entry_data = manifest.get(entry) or manifest.get(f"src/{entry}")
    if entry_data:
        css_files = entry_data.get("css", [])
        for css_file in css_files:
            tags.append(f'<link rel="stylesheet" href="/static/core/spa/{css_file}">')

    if not tags:
        style_entry = manifest.get("style.css") or manifest.get("src/style.css")
        if style_entry:
            tags.append(f'<link rel="stylesheet" href="/static/core/spa/{style_entry["file"]}">')

    return mark_safe("\n    ".join(tags)) if tags else ""


def _collect_imports(manifest, entry_key, collected=None, include_dynamic=False):
    """Recursively collect all imports for an entry."""
    if collected is None:
        collected = set()

    entry_data = manifest.get(entry_key)
    if not entry_data:
        return collected

    for imp in entry_data.get("imports", []):
        if imp not in collected:
            collected.add(imp)
            _collect_imports(manifest, imp, collected, include_dynamic)

    if include_dynamic:
        for dynamic_imp in entry_data.get("dynamicImports", []):
            if dynamic_imp not in collected:
                collected.add(dynamic_imp)
                _collect_imports(manifest, dynamic_imp, collected, include_dynamic)

    return collected


@register.simple_tag
def vite_prefetch(entry, include_dynamic=True):
    """Output prefetch links for an entry and its dependencies.

    Prefetch is non-blocking - browser fetches at low priority during idle time.
    The crossorigin attribute ensures cache reuse with module scripts.

    Args:
        entry: The entry point to prefetch (e.g., "src/app.js")
        include_dynamic: If True, also prefetch dynamically imported chunks
    """
    manifest = _load_manifest()
    if not manifest:
        return ""

    tags = []
    prefetched = set()

    entry_data = manifest.get(entry) or manifest.get(f"src/{entry}")
    if entry_data:
        file_url = f'/static/core/spa/{entry_data["file"]}'
        tags.append(f'<link rel="prefetch" href="{file_url}" as="script" crossorigin>')
        prefetched.add(entry_data["file"])

        all_imports = _collect_imports(manifest, entry, include_dynamic=include_dynamic)
        for imp in all_imports:
            imp_data = manifest.get(imp)
            if imp_data and imp_data["file"] not in prefetched:
                file_url = f'/static/core/spa/{imp_data["file"]}'
                tags.append(f'<link rel="prefetch" href="{file_url}" as="script" crossorigin>')
                prefetched.add(imp_data["file"])

    style_entry = manifest.get("style.css") or manifest.get("src/style.css")
    if style_entry and style_entry["file"] not in prefetched:
        tags.append(f'<link rel="prefetch" href="/static/core/spa/{style_entry["file"]}" as="style">')

    return mark_safe("\n    ".join(tags)) if tags else ""
