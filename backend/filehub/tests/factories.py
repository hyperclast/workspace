import factory

from filehub.constants import BlobStatus, FileUploadStatus, StorageProvider
from filehub.models import Blob, FileUpload
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class FileUploadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FileUpload

    uploaded_by = factory.SubFactory(UserFactory)
    project = factory.LazyAttribute(lambda o: ProjectFactory(creator=o.uploaded_by))
    status = FileUploadStatus.PENDING_URL
    filename = factory.Faker("file_name")
    content_type = "application/octet-stream"
    expected_size = factory.Faker("random_int", min=1024, max=10485760)
    checksum_sha256 = None
    metadata_json = factory.Dict({})


class BlobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Blob

    file_upload = factory.SubFactory(FileUploadFactory)
    provider = StorageProvider.R2
    bucket = "test-bucket"
    object_key = factory.Sequence(lambda n: f"uploads/file_{n}.bin")
    size_bytes = None
    etag = None
    checksum_sha256 = None
    status = BlobStatus.PENDING
    verified = None
