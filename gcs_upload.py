import os
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from google.cloud import storage


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class SignedUpload:
    bucket: str
    object_name: str
    gcs_uri: str
    signed_url: str
    method: str = "PUT"


def get_upload_bucket() -> str:
    bucket = os.getenv("GCS_UPLOAD_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("Defina GCS_UPLOAD_BUCKET para habilitar upload via GCS.")
    return bucket


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name.strip() or "arquivo"
    return _SAFE_NAME_RE.sub("_", base)


def build_object_name(filename: str, prefix: str | None = None) -> str:
    safe_name = sanitize_filename(filename)
    clean_prefix = (prefix or os.getenv("GCS_UPLOAD_PREFIX", "uploads")).strip("/")
    return f"{clean_prefix}/{uuid4().hex}/{safe_name}"


def create_signed_upload_url(
    filename: str,
    content_type: str = "application/octet-stream",
    expires_minutes: int = 30,
) -> SignedUpload:
    bucket_name = get_upload_bucket()
    object_name = build_object_name(filename)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expires_minutes),
        method="PUT",
        content_type=content_type,
    )

    return SignedUpload(
        bucket=bucket_name,
        object_name=object_name,
        gcs_uri=f"gs://{bucket_name}/{object_name}",
        signed_url=signed_url,
    )


def get_gcs_hmac_credentials() -> tuple[str | None, str | None]:
    key_id = os.getenv("GCS_HMAC_KEY_ID", "").strip() or None
    secret = os.getenv("GCS_HMAC_SECRET", "").strip() or None
    return key_id, secret
