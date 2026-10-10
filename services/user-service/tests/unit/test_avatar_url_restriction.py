from uuid import uuid4

from app.api.v1.user_endpoints import restrict_avatar_url

BUCKET = "documents"


def test_foreign_avatar_url_is_dropped():
    me = uuid4()
    data = {"first_name": "A", "avatar_url": f"s3://{BUCKET}/avatars/{uuid4()}/x.jpg"}
    restrict_avatar_url(data, me, BUCKET)
    assert "avatar_url" not in data
    assert data["first_name"] == "A"


def test_other_bucket_and_traversal_are_dropped():
    me = uuid4()
    for value in (
        f"s3://other-bucket/avatars/{me}/x.jpg",
        f"s3://{BUCKET}/avatars/{me}/../{uuid4()}/doc.pdf",
        f"s3://{BUCKET}/driver-documents/{me}/licence.pdf",
        "https://example.com/pic.jpg",
    ):
        data = {"avatar_url": value}
        restrict_avatar_url(data, me, BUCKET)
        assert "avatar_url" not in data, value


def test_own_avatar_url_is_kept():
    me = uuid4()
    value = f"s3://{BUCKET}/avatars/{me}/pic.jpg"
    data = {"avatar_url": value}
    restrict_avatar_url(data, me, BUCKET)
    assert data["avatar_url"] == value


def test_missing_avatar_is_untouched():
    data = {"first_name": "A"}
    restrict_avatar_url(data, uuid4(), BUCKET)
    assert data == {"first_name": "A"}
