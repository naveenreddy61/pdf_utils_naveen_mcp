"""Google Cloud Storage service for direct browser uploads and downloads.

Provides signed URLs so browsers can PUT large files to GCS (bypassing
Cloudflare's 100 MB proxy limit) and GET converted files the same way.
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


def _object_basename(original_filename: str) -> str:
    name = Path(original_filename).name or "download.bin"
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return safe or "download.bin"


def content_disposition_attachment(filename: str) -> str:
    """ASCII Content-Disposition for a signed URL query parameter."""
    return f'attachment; filename="{_object_basename(filename)}"'


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
    safe = _object_basename(original_filename)
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


def upload_and_sign_download(
    bucket_name: str,
    local_path: Path,
    download_as: str,
    content_type: str = "application/pdf",
    credentials_file: str | None = None,
    expiration_minutes: int = 15,
) -> tuple[str, str]:
    """Upload a local file and return (signed GET URL, object name).

    The signed URL carries response-content-disposition so a browser
    navigation downloads the file instead of previewing it. Caller should
    delete the object after the URL expires.
    """
    safe = _object_basename(download_as)
    gcs_object_name = f"temp-downloads/{uuid.uuid4().hex}_{safe}"
    disposition = content_disposition_attachment(download_as)

    client = _build_client(credentials_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_object_name)
    blob.content_type = content_type
    blob.content_disposition = disposition
    blob.upload_from_filename(str(local_path))

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method="GET",
        response_disposition=disposition,
        response_type=content_type,
    )
    return signed_url, gcs_object_name
