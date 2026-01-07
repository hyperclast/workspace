import json
import unittest

from django.conf import settings
from django.test import TestCase, override_settings

from pages.api.projects import serialize_project, _get_project_select_related
from pages.models import Project
from pages.tests.factories import ProjectFactory
from users.models import OrgMember
from users.tests.factories import UserFactory


def requires_billing_feature(test_item):
    """Skip test class or method if billing feature is not enabled.

    Use this for tests that need to import private.billing.models or create
    OrgBilling records. For tests that just check conditional behavior based
    on PRIVATE_FEATURES setting, use @override_settings instead.
    """
    if "billing" not in getattr(settings, "PRIVATE_FEATURES", []):
        return unittest.skip("Requires billing feature to be enabled")(test_item)
    return test_item


class TestGetProjectSelectRelated(TestCase):
    """Test the _get_project_select_related helper function."""

    @override_settings(PRIVATE_FEATURES=[])
    def test_without_billing_feature_excludes_billing(self):
        """When billing feature is disabled, org__billing should not be in select_related."""
        fields = _get_project_select_related()
        self.assertIn("org", fields)
        self.assertIn("creator", fields)
        self.assertNotIn("org__billing", fields)

    @override_settings(PRIVATE_FEATURES=["billing"])
    def test_with_billing_feature_includes_billing(self):
        """When billing feature is enabled, org__billing should be in select_related."""
        fields = _get_project_select_related()
        self.assertIn("org", fields)
        self.assertIn("creator", fields)
        self.assertIn("org__billing", fields)

    @override_settings(PRIVATE_FEATURES=["pricing", "socratic"])
    def test_with_other_features_excludes_billing(self):
        """When other features are enabled but not billing, org__billing should not be included."""
        fields = _get_project_select_related()
        self.assertNotIn("org__billing", fields)


class TestProjectIsProSerialization(TestCase):
    """Test that serialize_project correctly returns is_pro status."""

    def test_project_without_billing_returns_is_pro_false(self):
        """Project with no OrgBilling record should return is_pro=False."""
        user = UserFactory()
        project = ProjectFactory(creator=user)

        result = serialize_project(project)

        self.assertFalse(result["org"]["is_pro"])

    @requires_billing_feature
    def test_project_with_free_billing_returns_is_pro_false(self):
        """Project with OrgBilling plan=free should return is_pro=False."""
        from private.billing.models import OrgBilling, PlanChoices

        user = UserFactory()
        project = ProjectFactory(creator=user)

        # Create billing record with FREE plan
        OrgBilling.objects.create(org=project.org, plan=PlanChoices.FREE)

        # Refresh to get the billing relation
        project.refresh_from_db()

        result = serialize_project(project)

        self.assertFalse(result["org"]["is_pro"])

    @requires_billing_feature
    def test_project_with_pro_billing_returns_is_pro_true(self):
        """Project with OrgBilling plan=pro should return is_pro=True."""
        from private.billing.models import OrgBilling, PlanChoices

        user = UserFactory()
        project = ProjectFactory(creator=user)

        # Create billing record with PRO plan
        OrgBilling.objects.create(org=project.org, plan=PlanChoices.PRO)

        # Refresh to get the billing relation
        project.refresh_from_db()

        result = serialize_project(project)

        self.assertTrue(result["org"]["is_pro"])

    @requires_billing_feature
    def test_project_with_select_related_billing_returns_is_pro_true(self):
        """Test that select_related properly fetches billing for is_pro."""
        from private.billing.models import OrgBilling, PlanChoices

        user = UserFactory()
        project = ProjectFactory(creator=user)

        # Create billing record with PRO plan
        OrgBilling.objects.create(org=project.org, plan=PlanChoices.PRO)

        # Fetch with select_related like the API does
        project = Project.objects.select_related("org", "org__billing", "creator").get(id=project.id)

        result = serialize_project(project)

        self.assertTrue(result["org"]["is_pro"])


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class TestProjectsAPIIsProResponse(TestCase):
    """Test the full API response includes correct is_pro through schema serialization."""

    def test_api_returns_is_pro_false_without_billing(self):
        """API should return is_pro=false when org has no billing record."""
        user = UserFactory()
        project = ProjectFactory(creator=user)
        OrgMember.objects.create(org=project.org, user=user)

        self.client.force_login(user)
        response = self.client.get("/api/projects/?details=full")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertFalse(data[0]["org"]["is_pro"])

    @requires_billing_feature
    def test_api_returns_is_pro_true_with_pro_billing(self):
        """API should return is_pro=true when org has Pro billing - tests full schema serialization."""
        from private.billing.models import OrgBilling, PlanChoices

        user = UserFactory()
        project = ProjectFactory(creator=user)
        OrgMember.objects.create(org=project.org, user=user)

        # Create Pro billing
        OrgBilling.objects.create(org=project.org, plan=PlanChoices.PRO)

        self.client.force_login(user)
        response = self.client.get("/api/projects/?details=full")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        # This is the critical test - it goes through full Django Ninja schema serialization
        self.assertTrue(data[0]["org"]["is_pro"], "is_pro should be True in API JSON response")

    @requires_billing_feature
    def test_api_returns_is_pro_false_with_free_billing(self):
        """API should return is_pro=false when org has Free billing."""
        from private.billing.models import OrgBilling, PlanChoices

        user = UserFactory()
        project = ProjectFactory(creator=user)
        OrgMember.objects.create(org=project.org, user=user)

        # Create Free billing
        OrgBilling.objects.create(org=project.org, plan=PlanChoices.FREE)

        self.client.force_login(user)
        response = self.client.get("/api/projects/?details=full")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertFalse(data[0]["org"]["is_pro"])
