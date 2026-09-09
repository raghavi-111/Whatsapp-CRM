import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from organizations.models import create_organization_for_user

from .models import Media


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MediaApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="media@example.com", password="test-pass-123")
        self.organization = create_organization_for_user(self.user, "Media Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_upload_lists_media_for_current_organization(self):
        upload = SimpleUploadedFile("sample.png", b"\x89PNG\r\n\x1a\ncontent", content_type="image/png")
        response = self.client.post("/api/media/upload/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["media_type"], "image")
        self.assertEqual(response.data["original_filename"], "sample.png")
        self.assertTrue(Media.objects.filter(id=response.data["id"], organization=self.organization).exists())
        self.assertEqual([item["id"] for item in self.client.get("/api/media/").data], [response.data["id"]])

    def test_rejects_mime_spoofing(self):
        upload = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        response = self.client.post("/api/media/upload/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_list_does_not_expose_another_organization_media(self):
        other_user = get_user_model().objects.create_user(email="other-media@example.com")
        other_organization = create_organization_for_user(other_user, "Other Media Test")
        Media.objects.create(
            organization=other_organization,
            file=SimpleUploadedFile("other.pdf", b"%PDF-1.7\n"),
            filename="other.pdf", mime_type="application/pdf", media_type="document", size=9,
            created_by=other_user,
        )
        self.assertEqual(self.client.get("/api/media/").data, [])
