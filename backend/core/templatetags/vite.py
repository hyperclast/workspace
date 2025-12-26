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
