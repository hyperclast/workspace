from django.test import TestCase

from users.models import PersonalEmailDomain
from users.utils import (
    extract_domain_from_email,
    extract_org_name_from_domain,
    is_personal_email,
)


class TestIsPersonalEmail(TestCase):
    """Test is_personal_email() function."""

    def setUp(self):
        """Create test data for personal email domains."""
        # Create personal email domain entries (get_or_create since migration may have created some)
        PersonalEmailDomain.objects.get_or_create(substring="gmail")
        PersonalEmailDomain.objects.get_or_create(substring="yahoo")
        PersonalEmailDomain.objects.get_or_create(substring="hotmail")
        PersonalEmailDomain.objects.get_or_create(substring="outlook")

    def test_gmail_is_personal(self):
        """Gmail addresses should be detected as personal."""
        self.assertTrue(is_personal_email("user@gmail.com"))

    def test_gmail_with_country_code_is_personal(self):
        """Gmail with country code should be detected as personal."""
        self.assertTrue(is_personal_email("user@gmail.co.uk"))
        self.assertTrue(is_personal_email("user@gmail.com.au"))

    def test_yahoo_is_personal(self):
        """Yahoo addresses should be detected as personal."""
        self.assertTrue(is_personal_email("user@yahoo.com"))
        self.assertTrue(is_personal_email("user@yahoo.co.in"))

    def test_hotmail_is_personal(self):
        """Hotmail addresses should be detected as personal."""
        self.assertTrue(is_personal_email("user@hotmail.com"))
        self.assertTrue(is_personal_email("user@hotmail.co.uk"))

    def test_outlook_is_personal(self):
        """Outlook addresses should be detected as personal."""
        self.assertTrue(is_personal_email("user@outlook.com"))

    def test_company_email_is_not_personal(self):
        """Company email addresses should not be detected as personal."""
        self.assertFalse(is_personal_email("user@acme.com"))
        self.assertFalse(is_personal_email("user@company.org"))
        self.assertFalse(is_personal_email("user@business.co.uk"))

    def test_subdomain_company_email_is_not_personal(self):
        """Company email with subdomains should not be detected as personal."""
        self.assertFalse(is_personal_email("user@mail.company.com"))
        self.assertFalse(is_personal_email("user@corp.acme.com"))

    def test_invalid_email_treated_as_personal(self):
        """Invalid emails should be treated as personal (no org matching)."""
        self.assertTrue(is_personal_email("invalid"))
        self.assertTrue(is_personal_email("no-at-sign.com"))

    def test_empty_email_treated_as_personal(self):
        """Empty emails should be treated as personal."""
        self.assertTrue(is_personal_email(""))
        self.assertTrue(is_personal_email(None))

    def test_case_insensitive_matching(self):
        """Email matching should be case-insensitive."""
        self.assertTrue(is_personal_email("USER@GMAIL.COM"))
        self.assertTrue(is_personal_email("User@Yahoo.Com"))
        self.assertFalse(is_personal_email("USER@ACME.COM"))

    def test_substring_matching(self):
        """Domain substrings should match within the domain."""
        # gmail should match gmail.com, mail.gmail.com, etc
        self.assertTrue(is_personal_email("user@mail.gmail.com"))
        self.assertTrue(is_personal_email("user@gmail.example.com"))

    def test_partial_match_in_company_domain(self):
        """Personal substring in company domain should still match."""
        # If company is called "yahoofinance.com", it should still be personal
        # because it contains "yahoo"
        self.assertTrue(is_personal_email("user@yahoofinance.com"))

    def test_manual_overrides(self):
        """Manual overrides should take precedence."""
        from users.utils import PERSONAL_EMAIL_OVERRIDES

        # Add a manual override
        PERSONAL_EMAIL_OVERRIDES.add("special-company.com")

        self.assertTrue(is_personal_email("user@special-company.com"))

        # Clean up
        PERSONAL_EMAIL_OVERRIDES.remove("special-company.com")

    def test_multiple_personal_domains(self):
        """Multiple personal email domains should all be detected."""
        emails_should_be_personal = [
            "user@gmail.com",
            "user@yahoo.com",
            "user@hotmail.com",
            "user@outlook.com",
        ]

        for email in emails_should_be_personal:
            with self.subTest(email=email):
                self.assertTrue(is_personal_email(email))


class TestExtractOrgNameFromDomain(TestCase):
    """Test extract_org_name_from_domain() function."""

    def test_simple_com_domain(self):
        """Simple .com domain should extract company name."""
        self.assertEqual(extract_org_name_from_domain("acme.com"), "acme")
        self.assertEqual(extract_org_name_from_domain("company.com"), "company")
        self.assertEqual(extract_org_name_from_domain("business.com"), "business")

    def test_subdomain_with_com(self):
        """Subdomain with .com should extract company name, not subdomain."""
        self.assertEqual(extract_org_name_from_domain("mail.acme.com"), "acme")
        self.assertEqual(extract_org_name_from_domain("www.company.com"), "company")
        self.assertEqual(extract_org_name_from_domain("app.business.com"), "business")

    def test_multiple_subdomains(self):
        """Multiple subdomains should still extract company name."""
        self.assertEqual(extract_org_name_from_domain("mail.corp.acme.com"), "acme")
        self.assertEqual(extract_org_name_from_domain("dev.api.company.com"), "company")

    def test_non_com_tld(self):
        """Non-.com TLDs should use first part."""
        self.assertEqual(extract_org_name_from_domain("acme.co.uk"), "acme")
        self.assertEqual(extract_org_name_from_domain("company.org"), "company")
        self.assertEqual(extract_org_name_from_domain("business.net"), "business")
        self.assertEqual(extract_org_name_from_domain("startup.io"), "startup")

    def test_country_code_tlds(self):
        """Country code TLDs should extract first part."""
        self.assertEqual(extract_org_name_from_domain("acme.co.uk"), "acme")
        self.assertEqual(extract_org_name_from_domain("company.com.au"), "company")
        self.assertEqual(extract_org_name_from_domain("business.co.in"), "business")

    def test_empty_domain(self):
        """Empty domain should return None."""
        self.assertIsNone(extract_org_name_from_domain(""))
        self.assertIsNone(extract_org_name_from_domain(None))

    def test_single_part_domain(self):
        """Single-part domain (no dots) should return as-is."""
        self.assertEqual(extract_org_name_from_domain("localhost"), "localhost")

    def test_case_normalization(self):
        """Domain names should be lowercased."""
        self.assertEqual(extract_org_name_from_domain("ACME.COM"), "acme")
        self.assertEqual(extract_org_name_from_domain("Company.Com"), "company")

    def test_whitespace_handling(self):
        """Whitespace should be stripped."""
        self.assertEqual(extract_org_name_from_domain("  acme.com  "), "acme")
        self.assertEqual(extract_org_name_from_domain(" company.org "), "company")

    def test_special_tlds(self):
        """Special TLDs should use first part."""
        self.assertEqual(extract_org_name_from_domain("startup.ai"), "startup")
        self.assertEqual(extract_org_name_from_domain("company.tech"), "company")
        self.assertEqual(extract_org_name_from_domain("business.dev"), "business")

    def test_edu_domains(self):
        """Educational domains should extract institution name."""
        self.assertEqual(extract_org_name_from_domain("stanford.edu"), "stanford")
        self.assertEqual(extract_org_name_from_domain("mit.edu"), "mit")

    def test_gov_domains(self):
        """Government domains should extract first part."""
        self.assertEqual(extract_org_name_from_domain("agency.gov"), "agency")


class TestExtractDomainFromEmail(TestCase):
    """Test extract_domain_from_email() function."""

    def setUp(self):
        """Create test data for personal email domains."""
        PersonalEmailDomain.objects.get_or_create(substring="gmail")
        PersonalEmailDomain.objects.get_or_create(substring="yahoo")

    def test_company_email_returns_domain(self):
        """Company email should return domain."""
        self.assertEqual(extract_domain_from_email("user@acme.com"), "acme.com")
        self.assertEqual(extract_domain_from_email("user@company.org"), "company.org")

    def test_personal_email_returns_none(self):
        """Personal email should return None (no org matching)."""
        self.assertIsNone(extract_domain_from_email("user@gmail.com"))
        self.assertIsNone(extract_domain_from_email("user@yahoo.com"))

    def test_invalid_email_returns_none(self):
        """Invalid email should return None."""
        self.assertIsNone(extract_domain_from_email("invalid"))
        self.assertIsNone(extract_domain_from_email("no-at-sign.com"))

    def test_empty_email_returns_none(self):
        """Empty email should return None."""
        self.assertIsNone(extract_domain_from_email(""))
        self.assertIsNone(extract_domain_from_email(None))

    def test_domain_is_lowercased(self):
        """Extracted domain should be lowercased."""
        self.assertEqual(extract_domain_from_email("USER@ACME.COM"), "acme.com")
        self.assertEqual(extract_domain_from_email("User@Company.Org"), "company.org")

    def test_subdomain_preserved(self):
        """Full domain including subdomains should be returned."""
        self.assertEqual(extract_domain_from_email("user@mail.acme.com"), "mail.acme.com")
        self.assertEqual(extract_domain_from_email("user@corp.company.org"), "corp.company.org")

    def test_multiple_at_signs(self):
        """Email with multiple @ should handle gracefully."""
        # Should split on first @ and take everything after
        # This shouldn't crash - we just verify we get some result (or None)
        result = extract_domain_from_email("user@domain@acme.com")
        # Just verify it doesn't crash - result can be anything
        self.assertTrue(result is None or isinstance(result, str))


class TestEmailUtilsIntegration(TestCase):
    """Integration tests combining multiple utilities."""

    def setUp(self):
        """Create test data."""
        PersonalEmailDomain.objects.get_or_create(substring="gmail")
        PersonalEmailDomain.objects.get_or_create(substring="yahoo")

    def test_company_email_workflow(self):
        """Complete workflow for company email."""
        email = "alice@acme.com"

        # Should be detected as company email
        self.assertFalse(is_personal_email(email))

        # Should extract domain
        domain = extract_domain_from_email(email)
        self.assertEqual(domain, "acme.com")

        # Should extract org name
        org_name = extract_org_name_from_domain(domain)
        self.assertEqual(org_name, "acme")

    def test_personal_email_workflow(self):
        """Complete workflow for personal email."""
        email = "user@gmail.com"

        # Should be detected as personal
        self.assertTrue(is_personal_email(email))

        # Should not extract domain (returns None)
        domain = extract_domain_from_email(email)
        self.assertIsNone(domain)

    def test_subdomain_company_email_workflow(self):
        """Complete workflow for company email with subdomain."""
        email = "alice@mail.company.com"

        # Should be detected as company email
        self.assertFalse(is_personal_email(email))

        # Should extract full domain
        domain = extract_domain_from_email(email)
        self.assertEqual(domain, "mail.company.com")

        # Should extract company name (not subdomain)
        org_name = extract_org_name_from_domain(domain)
        self.assertEqual(org_name, "company")

    def test_country_code_workflow(self):
        """Complete workflow for country-specific domain."""
        email = "user@company.co.uk"

        # Should be detected as company email
        self.assertFalse(is_personal_email(email))

        # Should extract domain
        domain = extract_domain_from_email(email)
        self.assertEqual(domain, "company.co.uk")

        # Should extract company name
        org_name = extract_org_name_from_domain(domain)
        self.assertEqual(org_name, "company")


class TestPersonalEmailDomainModel(TestCase):
    """Test PersonalEmailDomain model."""

    def test_create_personal_email_domain(self):
        """Should be able to create PersonalEmailDomain entry."""
        domain, created = PersonalEmailDomain.objects.get_or_create(substring="testmail")
        self.assertEqual(domain.substring, "testmail")
        self.assertIsNotNone(domain.created)
        self.assertIsNotNone(domain.modified)

    def test_unique_constraint(self):
        """Duplicate substrings should raise error."""
        PersonalEmailDomain.objects.get_or_create(substring="unique-test-domain")

        with self.assertRaises(Exception):
            PersonalEmailDomain.objects.create(substring="unique-test-domain")

    def test_string_representation(self):
        """String representation should return substring."""
        domain, _ = PersonalEmailDomain.objects.get_or_create(substring="testmail2")
        self.assertEqual(str(domain), "testmail2")

    def test_query_by_substring(self):
        """Should be able to query by substring."""
        PersonalEmailDomain.objects.get_or_create(substring="gmail")
        PersonalEmailDomain.objects.get_or_create(substring="yahoo")

        result = PersonalEmailDomain.objects.filter(substring="gmail").first()
        self.assertIsNotNone(result)
        self.assertEqual(result.substring, "gmail")

    def test_bulk_create_with_ignore_conflicts(self):
        """Should support bulk_create with ignore_conflicts."""
        PersonalEmailDomain.objects.get_or_create(substring="bulk-test-1")

        # Try to bulk create including existing entry
        domains = [
            PersonalEmailDomain(substring="bulk-test-1"),  # Already exists
            PersonalEmailDomain(substring="bulk-test-2"),  # New
        ]

        PersonalEmailDomain.objects.bulk_create(domains, ignore_conflicts=True)

        # Should have the entry that was added
        self.assertTrue(PersonalEmailDomain.objects.filter(substring="bulk-test-1").exists())
        self.assertTrue(PersonalEmailDomain.objects.filter(substring="bulk-test-2").exists())
