import os
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import google.auth
from google.auth.transport.requests import Request
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


def _get_signing_identity() -> tuple[str | None, str | None]:
    """Return service account email and access token for IAM-backed URL signing.

    Cloud Run and Compute Engine use token-based application default credentials,
    not JSON keys with local private keys. Passing service_account_email and
    access_token lets google-cloud-storage use IAM Credentials signBlob instead
    of trying to sign locally.
    """
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    request = Request()
    credentials.refresh(request)

    service_account_email = getattr(credentials, "service_account_email", None)
    if not service_account_email:
        service_account_email = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", "").strip() or None

    return service_account_email, credentials.token


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

    kwargs = {
        "version": "v4",
        "expiration": timedelta(minutes=expires_minutes),
        "method": "PUT",
        "content_type": content_type,
    }

    try:
        signed_url = blob.generate_signed_url(**kwargs)
    except Exception as first_error:
        service_account_email, access_token = _get_signing_identity()
        if not service_account_email or not access_token:
            raise RuntimeError(
                "Falha ao gerar signed URL: credenciais do runtime não possuem "
                "chave privada local e não foi possível descobrir a service account. "
                "Defina GOOGLE_SERVICE_ACCOUNT_EMAIL ou use uma service account dedicada. "
                f"Erro original: {first_error}"
            ) from first_error

        try:
            signed_url = blob.generate_signed_url(
                **kwargs,
                service_account_email=service_account_email,
                access_token=access_token,
            )
        except Exception as second_error:
            raise RuntimeError(
                "Falha ao gerar signed URL via IAM. Garanta que a service account "
                f"{service_account_email} tenha roles/iam.serviceAccountTokenCreator "
                "e permissão no bucket de upload. "
                f"Erro original: {second_error}"
            ) from second_error

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
