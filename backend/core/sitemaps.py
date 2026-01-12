from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static public pages."""

    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return [
            ("core:home", 1.0),
            ("core:about", 0.8),
            ("core:pricing", 0.8),
            ("core:vs_index", 0.8),
            ("core:vs_notion", 0.7),
            ("core:vs_confluence", 0.7),
            ("core:vs_obsidian", 0.7),
            ("updates:list", 0.7),
            ("core:privacy", 0.4),
            ("core:terms", 0.4),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class DevPortalSitemap(Sitemap):
    """Sitemap for developer portal pages."""

    changefreq = "monthly"
    protocol = "https"
    priority = 0.6

    def items(self):
        return [
            "core:dev_index",
            "core:cli_docs",
            "core:oss_index",
        ]

    def location(self, item):
        return reverse(item)


class APIDocsSitemap(Sitemap):
    """Sitemap for API documentation pages."""

    changefreq = "monthly"
    protocol = "https"
    priority = 0.5

    def items(self):
        return ["overview", "ask", "orgs", "projects", "pages", "users"]

    def location(self, item):
        return reverse("core:api_docs", args=[item])


class OSSRepoSitemap(Sitemap):
    """Sitemap for OSS repository pages."""

    changefreq = "monthly"
    protocol = "https"
    priority = 0.5

    def items(self):
        return ["workspace", "firebreak", "filehub"]

    def location(self, item):
        return reverse("core:oss_repo", args=[item])


class UpdatesSitemap(Sitemap):
    """Sitemap for product updates."""

    changefreq = "weekly"
    protocol = "https"
    priority = 0.6

    def items(self):
        from updates.models import Update

        return Update.objects.filter(is_published=True)

    def location(self, item):
        return reverse("updates:detail", args=[item.slug])

    def lastmod(self, item):
        return item.updated_at


sitemaps = {
    "static": StaticViewSitemap,
    "dev_portal": DevPortalSitemap,
    "api_docs": APIDocsSitemap,
    "oss": OSSRepoSitemap,
    "updates": UpdatesSitemap,
}
