import uuid
from backend.db.client import supabase

BUCKET_NAME = "legal documents"

def ensure_bucket_exists() -> None:
    """Create the storage bucket if it doesn't already exist."""
    existing = [b.name for b in supabase.storage.list_buckets()]
    if BUCKET_NAME not in existing:
        supabase.storage.create_bucket(BUCKET_NAME, options={"public": False})


def upload_pdf(file_bytes: bytes, original_filename: str, user_id: str) -> dict:
    """Upload a PDF to the documents bucket scoped to the user."""
    file_id = uuid.uuid4().hex
    storage_path = f"{user_id}/{file_id}/{original_filename}"

    ensure_bucket_exists()

    supabase.storage.from_(BUCKET_NAME).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"},
    )

    return {"bucket": BUCKET_NAME, "path": storage_path}


def list_files(user_id: str) -> list[dict]:
    """List all files belonging to a specific user in the bucket."""
    ensure_bucket_exists()
    return supabase.storage.from_(BUCKET_NAME).list(path=user_id)


def get_signed_url(path: str, expires_in: int = 3600) -> str:
    """Generate a temporary signed URL for a stored file."""
    res = supabase.storage.from_(BUCKET_NAME).create_signed_url(path, expires_in)
    return res["signedURL"]


def delete_file(path: str) -> None:
    """Delete a file from the bucket."""
    supabase.storage.from_(BUCKET_NAME).remove([path])
