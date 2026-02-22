"""Google Cloud Storage service for direct browser uploads.

Provides signed URLs so browsers can upload files directly to GCS,
bypassing Cloudflare's 100 MB proxy limit entirely.
"""

import uuid
import datetime
import asyncio
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account


def _build_client(credentials_file: str | None) -> storage.Client:
    """Build a GCS client using a service account JSON file or ADC."""
    if credentials_file:
        creds = service_account.Credentials.from_service_account_file(credentials_file)
        return storage.Client(credentials=creds)
    # Falls back to Application Default Credentials (ADC) or GOOGLE_APPLICATION_CREDENTIALS env
    return storage.Client()


def generate_upload_signed_url(
    bucket_name: str,
    original_filename: str,
    content_type: str,
    credentials_file: str | None = None,
    expiration_minutes: int = 15,
) -> tuple[str, str]:
    """Generate a signed URL for a direct browser PUT upload to GCS.

    Returns:
        (signed_url, gcs_object_name) tuple.
        The caller should pass gcs_object_name back on confirm-upload.
    """
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_filename)
    gcs_object_name = f"temp-uploads/{uuid.uuid4().hex}_{safe}"

    client = _build_client(credentials_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_object_name)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method="PUT",
        content_type=content_type,
    )
    return signed_url, gcs_object_name


async def download_from_gcs(
    bucket_name: str,
    gcs_object_name: str,
    local_path: Path,
    credentials_file: str | None = None,
) -> None:
    """Download a GCS object to a local path (runs blocking I/O in thread pool)."""
    def _download():
        client = _build_client(credentials_file)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        blob.download_to_filename(str(local_path))

    await asyncio.to_thread(_download)


async def delete_from_gcs(
    bucket_name: str,
    gcs_object_name: str,
    credentials_file: str | None = None,
) -> None:
    """Delete a GCS object (runs blocking I/O in thread pool)."""
    def _delete():
        client = _build_client(credentials_file)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        blob.delete()

    await asyncio.to_thread(_delete)
