"""Temporary signed links for fleet documents.

Fleet document responses used to carry a plain storage address built from the
bucket and file key. That address only works when the bucket allows public
reads, which exposes applicants' business documents. Responses now carry a
signed link that expires after an hour.
"""

from app.config import settings
from mediride_common.storage.s3_client import S3StorageClient

LINK_LIFETIME_SECONDS = 3600


async def sign_fleet_documents(s3_client: S3StorageClient, documents) -> None:
    """Set file_url on each document response to a signed link."""
    for doc in documents or []:
        if getattr(doc, "file_key", None):
            doc.file_url = await s3_client.generate_presigned_url(
                bucket=settings.S3_BUCKET_DOCUMENTS,
                key=doc.file_key,
                expires_in=LINK_LIFETIME_SECONDS,
            )


async def sign_applications(s3_client: S3StorageClient, applications) -> None:
    """Sign the documents on one or many fleet application responses."""
    if not isinstance(applications, (list, tuple)):
        applications = [applications]
    for application in applications:
        await sign_fleet_documents(s3_client, application.documents)
