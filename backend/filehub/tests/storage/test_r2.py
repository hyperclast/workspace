from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from filehub.storage.r2 import R2StorageBackend, encode_content_disposition


class TestR2StorageBackend(TestCase):
    @override_settings(
        WS_FILEHUB_R2_ACCOUNT_ID="test-account",
        WS_FILEHUB_R2_ACCESS_KEY_ID="test-key",
        WS_FILEHUB_R2_SECRET_ACCESS_KEY="test-secret",
        WS_FILEHUB_R2_BUCKET="test-bucket",
    )
    @patch("filehub.storage.r2.boto3")
    def test_generate_upload_url(self, mock_boto3):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed-url.example.com"
        mock_boto3.client.return_value = mock_client

        backend = R2StorageBackend()
        url, headers = backend.generate_upload_url(
            bucket=None,
            object_key="test/file.txt",
            content_type="text/plain",
            content_length=100,
            expires_in=timedelta(minutes=10),
        )

        self.assertEqual(url, "https://signed-url.example.com")
        self.assertEqual(headers["Content-Type"], "text/plain")
        self.assertEqual(headers["Content-Length"], "100")
        mock_client.generate_presigned_url.assert_called_once()

    @override_settings(
        WS_FILEHUB_R2_ACCOUNT_ID="test-account",
        WS_FILEHUB_R2_ACCESS_KEY_ID="test-key",
        WS_FILEHUB_R2_SECRET_ACCESS_KEY="test-secret",
        WS_FILEHUB_R2_BUCKET="test-bucket",
    )
    @patch("filehub.storage.r2.boto3")
    def test_generate_download_url(self, mock_boto3):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://download-url.example.com"
        mock_boto3.client.return_value = mock_client

        backend = R2StorageBackend()
        url = backend.generate_download_url(
            bucket=None,
            object_key="test/file.txt",
            expires_in=timedelta(minutes=10),
        )

        self.assertEqual(url, "https://download-url.example.com")
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "test/file.txt"},
            ExpiresIn=600,
        )

    @override_settings(
        WS_FILEHUB_R2_ACCOUNT_ID="test-account",
        WS_FILEHUB_R2_ACCESS_KEY_ID="test-key",
        WS_FILEHUB_R2_SECRET_ACCESS_KEY="test-secret",
        WS_FILEHUB_R2_BUCKET="test-bucket",
    )
    @patch("filehub.storage.r2.boto3")
    def test_generate_download_url_with_filename(self, mock_boto3):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://download-url.example.com"
        mock_boto3.client.return_value = mock_client

        backend = R2StorageBackend()
        url = backend.generate_download_url(
            bucket=None,
            object_key="test/file.txt",
            expires_in=timedelta(minutes=10),
            filename="custom-name.txt",
        )

        self.assertEqual(url, "https://download-url.example.com")
        call_args = mock_client.generate_presigned_url.call_args
        self.assertIn("ResponseContentDisposition", call_args[1]["Params"])

    @override_settings(
        WS_FILEHUB_R2_ACCOUNT_ID="test-account",
        WS_FILEHUB_R2_ACCESS_KEY_ID="test-key",
        WS_FILEHUB_R2_SECRET_ACCESS_KEY="test-secret",
        WS_FILEHUB_R2_BUCKET="test-bucket",
    )
    @patch("filehub.storage.r2.boto3")
    def test_head_object(self, mock_boto3):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 12345,
            "ETag": '"abc123"',
            "ContentType": "image/png",
        }
        mock_boto3.client.return_value = mock_client

        backend = R2StorageBackend()
        result = backend.head_object(bucket=None, object_key="test/file.png")

        self.assertEqual(result["size_bytes"], 12345)
        self.assertEqual(result["etag"], "abc123")
        self.assertEqual(result["content_type"], "image/png")

    @override_settings(
        WS_FILEHUB_R2_ACCOUNT_ID="test-account",
        WS_FILEHUB_R2_ACCESS_KEY_ID="test-key",
        WS_FILEHUB_R2_SECRET_ACCESS_KEY="test-secret",
        WS_FILEHUB_R2_BUCKET="test-bucket",
    )
    @patch("filehub.storage.r2.boto3")
    def test_copy_object(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        backend = R2StorageBackend()
        backend.copy_object(
            source_bucket=None,
            source_key="source/file.txt",
            dest_bucket=None,
            dest_key="dest/file.txt",
        )

        mock_client.copy_object.assert_called_once_with(
            CopySource={"Bucket": "test-bucket", "Key": "source/file.txt"},
            Bucket="test-bucket",
            Key="dest/file.txt",
        )

    @override_settings(
        WS_FILEHUB_R2_ACCOUNT_ID="test-account",
        WS_FILEHUB_R2_ACCESS_KEY_ID="test-key",
        WS_FILEHUB_R2_SECRET_ACCESS_KEY="test-secret",
        WS_FILEHUB_R2_BUCKET="test-bucket",
    )
    @patch("filehub.storage.r2.boto3")
    def test_delete_object(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        backend = R2StorageBackend()
        backend.delete_object(bucket=None, object_key="test/file.txt")

        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.txt",
        )


class TestEncodeContentDisposition(TestCase):
    """Tests for the encode_content_disposition helper function."""

    def test_simple_ascii_filename(self):
        """Simple ASCII filename uses quoted format."""
        result = encode_content_disposition("document.pdf")
        self.assertEqual(result, 'attachment; filename="document.pdf"')

    def test_filename_with_spaces(self):
        """Filename with spaces is handled correctly."""
        result = encode_content_disposition("my document.pdf")
        self.assertEqual(result, 'attachment; filename="my document.pdf"')

    def test_filename_with_quotes_escaped(self):
        """Quotes in filename are escaped."""
        result = encode_content_disposition('file"name.txt')
        self.assertEqual(result, 'attachment; filename="file\\"name.txt"')

    def test_filename_with_backslash_escaped(self):
        """Backslashes in filename are escaped."""
        result = encode_content_disposition("file\\name.txt")
        self.assertEqual(result, 'attachment; filename="file\\\\name.txt"')

    def test_filename_with_multiple_special_chars(self):
        """Multiple special characters are all escaped."""
        result = encode_content_disposition('a"b\\c"d.txt')
        self.assertEqual(result, 'attachment; filename="a\\"b\\\\c\\"d.txt"')

    def test_unicode_filename_uses_rfc5987(self):
        """Unicode filename uses RFC 5987 encoding."""
        result = encode_content_disposition("文档.pdf")
        # Should have fallback filename and RFC 5987 encoded version
        self.assertIn('filename="download"', result)
        self.assertIn("filename*=UTF-8''", result)
        # Chinese characters should be percent-encoded
        self.assertIn("%E6%96%87%E6%A1%A3", result)

    def test_mixed_ascii_unicode_uses_rfc5987(self):
        """Mixed ASCII/Unicode filename uses RFC 5987 encoding."""
        result = encode_content_disposition("report_日本語.pdf")
        self.assertIn('filename="download"', result)
        self.assertIn("filename*=UTF-8''", result)

    def test_emoji_filename_uses_rfc5987(self):
        """Emoji in filename uses RFC 5987 encoding."""
        result = encode_content_disposition("🎉party.txt")
        self.assertIn('filename="download"', result)
        self.assertIn("filename*=UTF-8''", result)

    def test_cyrillic_filename_uses_rfc5987(self):
        """Cyrillic filename uses RFC 5987 encoding."""
        result = encode_content_disposition("документ.pdf")
        self.assertIn('filename="download"', result)
        self.assertIn("filename*=UTF-8''", result)
