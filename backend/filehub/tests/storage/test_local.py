from datetime import timedelta

from django.test import TestCase, override_settings

from filehub.storage.exceptions import ObjectNotFoundError
from filehub.storage.local import LocalStorageBackend


class TestLocalStorageBackend(TestCase):
    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
        WS_FILEHUB_LOCAL_BASE_URL="http://localhost:8000",
    )
    def test_put_and_head_object(self):
        backend = LocalStorageBackend()

        # Put an object
        result = backend.put_object(
            bucket=None,
            object_key="test/file.txt",
            body=b"Hello World",
        )

        # Verify put_object returns etag
        self.assertIn("etag", result)
        self.assertEqual(len(result["etag"]), 64)  # SHA256

        # Head it
        head_result = backend.head_object(bucket=None, object_key="test/file.txt")

        self.assertEqual(head_result["size_bytes"], 11)
        self.assertIn("etag", head_result)

        # Cleanup
        backend.delete_object(bucket=None, object_key="test/file.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_head_object_not_found(self):
        backend = LocalStorageBackend()

        with self.assertRaises(ObjectNotFoundError):
            backend.head_object(bucket=None, object_key="nonexistent/file.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_get_object(self):
        backend = LocalStorageBackend()

        # Put an object
        backend.put_object(
            bucket=None,
            object_key="test/get-file.txt",
            body=b"Test content",
        )

        # Get it
        data = backend.get_object("test/get-file.txt")
        self.assertEqual(data, b"Test content")

        # Cleanup
        backend.delete_object(bucket=None, object_key="test/get-file.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_get_object_not_found(self):
        backend = LocalStorageBackend()

        with self.assertRaises(ObjectNotFoundError):
            backend.get_object("nonexistent/file.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_copy_object(self):
        backend = LocalStorageBackend()

        # Put source
        backend.put_object(
            bucket=None,
            object_key="source/file.txt",
            body=b"Copy me",
        )

        # Copy
        backend.copy_object(
            source_bucket=None,
            source_key="source/file.txt",
            dest_bucket=None,
            dest_key="dest/file.txt",
        )

        # Verify dest exists
        result = backend.head_object(bucket=None, object_key="dest/file.txt")
        self.assertEqual(result["size_bytes"], 7)

        # Cleanup
        backend.delete_object(bucket=None, object_key="source/file.txt")
        backend.delete_object(bucket=None, object_key="dest/file.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_copy_object_not_found(self):
        backend = LocalStorageBackend()

        with self.assertRaises(ObjectNotFoundError):
            backend.copy_object(
                source_bucket=None,
                source_key="nonexistent/file.txt",
                dest_bucket=None,
                dest_key="dest/file.txt",
            )

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_delete_object_idempotent(self):
        backend = LocalStorageBackend()

        # Put an object
        backend.put_object(
            bucket=None,
            object_key="test/delete-me.txt",
            body=b"Delete me",
        )

        # Delete it
        backend.delete_object(bucket=None, object_key="test/delete-me.txt")

        # Delete again (should not raise)
        backend.delete_object(bucket=None, object_key="test/delete-me.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
        WS_FILEHUB_LOCAL_BASE_URL="http://localhost:8000",
    )
    def test_generate_upload_url(self):
        backend = LocalStorageBackend()

        url, headers = backend.generate_upload_url(
            bucket=None,
            object_key="test/upload.txt",
            content_type="text/plain",
            content_length=100,
            expires_in=None,
        )

        self.assertIn("/api/internal/upload-local/", url)
        self.assertIn("key=", url)
        self.assertIn("token=", url)
        self.assertEqual(headers["Content-Type"], "text/plain")
        self.assertEqual(headers["Content-Length"], "100")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
        WS_FILEHUB_LOCAL_BASE_URL="http://localhost:8000",
    )
    def test_generate_download_url(self):
        backend = LocalStorageBackend()

        url = backend.generate_download_url(
            bucket=None,
            object_key="test/download.txt",
            expires_in=timedelta(minutes=10),
        )

        self.assertIn("/api/internal/download-local/", url)
        self.assertIn("key=", url)
        self.assertIn("token=", url)

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
        WS_FILEHUB_LOCAL_BASE_URL="http://localhost:8000",
    )
    def test_generate_download_url_with_filename(self):
        backend = LocalStorageBackend()

        url = backend.generate_download_url(
            bucket=None,
            object_key="test/download.txt",
            expires_in=timedelta(minutes=10),
            filename="custom-name.txt",
        )

        self.assertIn("filename=custom-name.txt", url)

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_head_object_etag_is_sha256(self):
        """Verify ETag is SHA256 (64 hex chars) not MD5 (32 hex chars)."""
        backend = LocalStorageBackend()

        backend.put_object(
            bucket=None,
            object_key="test/sha256-etag.txt",
            body=b"Test content for SHA256",
        )

        result = backend.head_object(bucket=None, object_key="test/sha256-etag.txt")

        # SHA256 produces 64 hex characters, MD5 produces 32
        self.assertEqual(len(result["etag"]), 64)
        # Verify it's valid hex
        int(result["etag"], 16)

        # Cleanup
        backend.delete_object(bucket=None, object_key="test/sha256-etag.txt")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_put_object_with_content_type(self):
        """Test put_object accepts content_type parameter."""
        backend = LocalStorageBackend()

        result = backend.put_object(
            bucket=None,
            object_key="test/typed-file.zip",
            body=b"PK\x03\x04",  # ZIP magic bytes
            content_type="application/zip",
        )

        # Verify etag is returned
        self.assertIn("etag", result)
        self.assertEqual(len(result["etag"]), 64)

        # Cleanup
        backend.delete_object(bucket=None, object_key="test/typed-file.zip")

    @override_settings(
        WS_FILEHUB_LOCAL_STORAGE_ROOT="/tmp/filehub-test",
    )
    def test_put_object_creates_parent_directories(self):
        """Test put_object creates nested directories as needed."""
        backend = LocalStorageBackend()

        result = backend.put_object(
            bucket=None,
            object_key="deep/nested/path/file.txt",
            body=b"nested content",
        )

        self.assertIn("etag", result)

        # Verify file exists
        head_result = backend.head_object(bucket=None, object_key="deep/nested/path/file.txt")
        self.assertEqual(head_result["size_bytes"], 14)

        # Cleanup
        backend.delete_object(bucket=None, object_key="deep/nested/path/file.txt")
