"""
RQ tasks for import processing.
"""

import logging
import shutil
from pathlib import Path

from django.conf import settings

from core.helpers import task
from imports.exceptions import ImportArchiveBombError, ImportNoContentError
from imports.services.abuse import record_abuse
from imports.services.archive_safety import inspect_and_validate_archive

logger = logging.getLogger(__name__)


@task(settings.JOB_IMPORTS_QUEUE)
def process_notion_import(import_job_id: int):
    """
    Process a Notion import job asynchronously.

    This task:
    1. Updates job status to 'processing'
    2. Reads the uploaded zip file from the path stored in ImportArchive
    3. Parses and transforms the Notion export
    4. Creates pages in batch with link remapping
    5. Archives the original zip to R2
    6. Cleans up temp files
    7. Updates job status to 'completed' or 'failed'

    Args:
        import_job_id: Primary key of the ImportJob record
            (named import_job_id to avoid conflict with RQ's job_id parameter)
    """
    from imports.constants import ImportJobStatus
    from imports.models import ImportJob
    from imports.services.notion import (
        build_page_tree,
        create_import_pages,
        extract_zip,
        flatten_page_tree,
    )
    from imports.services.storage import archive_import_file

    temp_path = None
    extracted_path = None

    try:
        # Get the import job with its archive
        job = ImportJob.objects.select_related("archive").get(id=import_job_id)

        # Get temp file path from archive
        if not hasattr(job, "archive") or not job.archive:
            raise ValueError(f"Import job {import_job_id} has no associated archive")

        temp_file_path = job.archive.temp_file_path
        if not temp_file_path:
            raise ValueError(f"Import job {import_job_id} archive has no temp_file_path")

        temp_path = Path(temp_file_path)

        # Update status to processing
        job.status = ImportJobStatus.PROCESSING
        job.save(update_fields=["status"])

        logger.info(f"Processing import job {job.external_id} for user {job.user_id}")

        # Verify temp file exists
        if not temp_path.exists():
            raise FileNotFoundError(f"Temp file not found: {temp_file_path}")

        # Pre-extraction safety check for zip bombs and malicious archives
        logger.info(f"Inspecting archive for job {job.external_id}")
        inspection_result = inspect_and_validate_archive(temp_path, allow_notion_nested_zips=True)

        # Store inspection results in job metadata for observability
        if not job.metadata:
            job.metadata = {}
        job.metadata["archive_inspection"] = inspection_result.to_dict()
        job.save(update_fields=["metadata"])

        logger.info(
            f"Archive inspection passed for job {job.external_id}: "
            f"{inspection_result.file_count} files, "
            f"{inspection_result.compression_ratio:.1f}x ratio, "
            f"{inspection_result.uncompressed_size} bytes uncompressed"
        )

        # Read file content for archiving before extraction
        file_content = temp_path.read_bytes()

        # Extract the zip file
        extracted_path = extract_zip(temp_path.open("rb"))

        # Build page tree from extracted content
        parsed_pages = build_page_tree(extracted_path)

        # Update total pages count
        flat_pages = flatten_page_tree(parsed_pages)
        job.total_pages = len(flat_pages)
        job.save(update_fields=["total_pages"])

        logger.info(f"Found {job.total_pages} pages to import for job {job.external_id}")

        # Create pages with link remapping
        result = create_import_pages(
            parsed_pages=parsed_pages,
            project=job.project,
            user=job.user,
            import_job=job,
        )

        # Update progress counters
        job.pages_imported_count = result["stats"]["created"]
        job.pages_skipped_count = result["stats"]["skipped"]
        job.pages_failed_count = result["stats"]["failed"]
        job.save(update_fields=["pages_imported_count", "pages_skipped_count", "pages_failed_count"])

        # Fail if no content was imported or skipped (empty archive or unsupported formats only)
        if job.pages_imported_count == 0 and job.pages_skipped_count == 0:
            raise ImportNoContentError(
                "No importable content found in the archive. "
                "The archive may be empty or contain only unsupported file formats. "
                "Supported formats: Markdown (.md), CSV (.csv)"
            )

        # Archive the original zip to R2 and update the archive record
        try:
            archive_import_file(
                archive=job.archive,
                file_content=file_content,
            )
            logger.info(f"Archived import file for job {job.external_id}")
        except Exception as archive_error:
            # Log but don't fail the import if archiving fails
            logger.warning(f"Failed to archive import file for job {job.external_id}: {archive_error}")

        # Mark as completed
        job.status = ImportJobStatus.COMPLETED
        job.save(update_fields=["status"])

        logger.info(
            f"Import job {job.external_id} completed: "
            f"{job.pages_imported_count} imported, {job.pages_skipped_count} skipped (duplicates), "
            f"{job.pages_failed_count} failed"
        )

    except ImportJob.DoesNotExist:
        logger.error(f"Import job {import_job_id} not found")
        raise

    except ImportArchiveBombError as e:
        # Record abuse for zip bomb / malicious archive detection
        logger.warning(f"Import job {import_job_id} rejected due to archive safety: {e.reason}")

        try:
            job = ImportJob.objects.get(id=import_job_id)

            # Record abuse with request context from job
            record_abuse(
                user=job.user,
                reason=e.reason,
                details=e.details,
                import_job=job,
                ip_address=job.request_details.get("ip_address"),
                user_agent=job.request_details.get("user_agent", ""),
            )

            # Update job status to failed
            job.status = ImportJobStatus.FAILED
            job.error_message = str(e)[:1000]
            job.save(update_fields=["status", "error_message"])
        except Exception:
            pass

        raise

    except Exception as e:
        logger.exception(f"Import job {import_job_id} failed: {e}")

        # Update job status to failed
        try:
            job = ImportJob.objects.get(id=import_job_id)
            job.status = ImportJobStatus.FAILED
            job.error_message = str(e)[:1000]  # Truncate long error messages
            job.save(update_fields=["status", "error_message"])
        except Exception:
            pass

        raise

    finally:
        # Clean up temp file
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temp file {temp_path}: {cleanup_error}")

        # Clear temp_file_path from archive after cleanup
        try:
            if job and hasattr(job, "archive") and job.archive:
                job.archive.temp_file_path = None
                job.archive.save(update_fields=["temp_file_path"])
        except Exception:
            pass

        # Clean up extracted directory
        if extracted_path and extracted_path.exists():
            try:
                shutil.rmtree(extracted_path)
                logger.debug(f"Cleaned up extracted directory: {extracted_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up extracted directory {extracted_path}: {cleanup_error}")
