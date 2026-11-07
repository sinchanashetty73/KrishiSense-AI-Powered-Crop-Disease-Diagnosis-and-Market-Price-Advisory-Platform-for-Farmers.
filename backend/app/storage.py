"""Image storage. Uses S3 when S3_BUCKET is set, otherwise the local UPLOAD_DIR.
Keys start with "scans/" (private, never served) or "listings/" (marketplace photos, served by /api/media)."""
import uuid
from pathlib import Path

from .config import settings

PUBLIC_PREFIX = "listings/"


def save_image(user_id: int, data: bytes, ext: str, prefix: str = "scans") -> str:
    key = f"{prefix}/{user_id}/{uuid.uuid4().hex}{ext}"
    if settings.s3_bucket:
        import boto3  # credentials come from the ECS task role / EC2 instance role

        boto3.client("s3", region_name=settings.aws_region).put_object(
            Bucket=settings.s3_bucket, Key=key, Body=data)
    else:
        path = Path(settings.upload_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return key


def public_url(key: str | None) -> str | None:
    """URL the browser can use for a marketplace photo."""
    if not key or not key.startswith(PUBLIC_PREFIX):
        return None
    if settings.s3_bucket:
        import boto3
        return boto3.client("s3", region_name=settings.aws_region).generate_presigned_url(
            "get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=3600)
    return f"/api/media/{key}"


def local_path(key: str) -> Path | None:
    """Safe local path for a public key (blocks path traversal and private prefixes)."""
    if not key.startswith(PUBLIC_PREFIX) or ".." in key or key.startswith("/"):
        return None
    base = Path(settings.upload_dir).resolve()
    p = (base / key).resolve()
    return p if base in p.parents and p.is_file() else None
