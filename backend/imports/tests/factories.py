import factory

from imports.constants import ImportJobStatus, ImportProvider, Severity
from imports.models import ImportAbuseRecord, ImportArchive, ImportBannedUser, ImportedPage, ImportJob
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import UserFactory


class ImportJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImportJob

    user = factory.SubFactory(UserFactory)
    project = factory.SubFactory(ProjectFactory)
    provider = ImportProvider.NOTION
    status = ImportJobStatus.PENDING
    total_pages = 0
    pages_imported_count = 0
    pages_failed_count = 0
    error_message = ""
    metadata = factory.Dict({})
    request_details = factory.Dict({})


class ImportArchiveFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImportArchive

    import_job = factory.SubFactory(ImportJobFactory)
    provider = "r2"
    bucket = "imports"
    object_key = factory.LazyAttribute(lambda o: f"archives/{o.import_job.external_id}/{o.filename}")
    filename = factory.Faker("file_name", extension="zip")
    content_type = "application/zip"
    size_bytes = factory.Faker("random_int", min=1024, max=104857600)
    etag = factory.Faker("md5")


class ImportedPageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImportedPage

    import_job = factory.SubFactory(ImportJobFactory)
    page = factory.SubFactory(PageFactory)
    # Denormalized from import_job.project for efficient unique constraint
    project = factory.LazyAttribute(lambda o: o.import_job.project)
    original_path = factory.Faker("file_path", depth=3, extension="md")
    source_hash = factory.Faker("hexify", text="^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")


class ImportAbuseRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImportAbuseRecord

    user = factory.SubFactory(UserFactory)
    import_job = factory.SubFactory(ImportJobFactory)
    reason = "compression_ratio"
    details = factory.Dict({"compression_ratio": 50.0})
    ip_address = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")
    severity = Severity.MEDIUM


class ImportBannedUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImportBannedUser

    user = factory.SubFactory(UserFactory)
    reason = "Auto-banned: critical_threshold_exceeded. Counts: {'critical': 1}"
    enforced = True
