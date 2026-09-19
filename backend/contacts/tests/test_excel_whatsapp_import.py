import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from accounts.models import User
from automations.models import AutomationLog
from contacts.models import Contact, ContactCategory
from contacts.services.excel_whatsapp_import import WorkbookError, commit, inspect_sheet, preview, store_workbook
from conversations.models import Conversation, Message
from organizations.models import Organization, OrganizationMember


class ExcelWhatsAppImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="excel@example.com", password="password")
        self.organization = Organization.objects.create(name="Excel Org", slug="excel-org", owner=self.user)
        OrganizationMember.objects.get_or_create(organization=self.organization, user=self.user, defaults={"role": "owner", "status": "active"})
        self.unknown = ContactCategory.objects.create(organization=self.organization, name="Unknown")
        self.hotels = ContactCategory.objects.create(organization=self.organization, name="Hotels & Resorts")

    def upload(self, sheets):
        book = Workbook(); book.remove(book.active)
        for name, rows in sheets:
            ws = book.create_sheet(name)
            for row in rows: ws.append(row)
        output = io.BytesIO(); book.save(output)
        return store_workbook(self.user, self.organization, SimpleUploadedFile("contacts.xlsx", output.getvalue()))

    def test_sheet_discovery_autoselection_unicode_and_mapping(self):
        uploaded = self.upload([("Résumé", [["Résumé", "Téléphone"], ["Hôtel", "+91 98765 43210"]]), ("WhatsApp Contacts", [["Business Name", "WhatsApp Number", "Category"], ["Hotel A", "+91 98765 43210", "hotels & resorts"]])])
        self.assertEqual(uploaded["selected_sheet"], "WhatsApp Contacts")
        self.assertEqual(uploaded["sheet"]["suggested_mappings"]["whatsapp_number"], "WhatsApp Number")
        other = inspect_sheet(uploaded["token"], self.user, self.organization, "Résumé")
        self.assertEqual(other["headers"], ["Résumé", "Téléphone"])

    def test_generic_preview_is_read_only_and_commit_is_idempotent(self):
        uploaded = self.upload([("Sheet1", [[None, None], ["Name", "Mobile", "Type"], ["Hotel A", "+91 98765 43210", "hotels & resorts"], ["Duplicate", "919876543210", "Other"], ["Bad", "abc", "Other"]])])
        args = (uploaded["token"], self.user, self.organization, "Sheet1", {"business_name": "Name", "whatsapp_number": "Mobile", "category": "Type"}, self.unknown.id, True)
        result = preview(*args)
        self.assertEqual(result["summary"]["new"], 1); self.assertEqual(result["summary"]["duplicates"], 1); self.assertEqual(result["summary"]["invalid"], 1)
        self.assertEqual(Contact.objects.count(), 0)
        first = commit(*args); second = commit(*args)
        self.assertEqual(first["summary"]["created"], 1); self.assertEqual(second["summary"]["created"], 0)
        self.assertEqual(Contact.objects.count(), 1); self.assertEqual(Contact.objects.get().category, self.hotels)
        self.assertEqual(Conversation.objects.count(), 0); self.assertEqual(Message.objects.count(), 0); self.assertEqual(AutomationLog.objects.count(), 0)

    def test_rejects_non_xlsx_and_requires_confirmation(self):
        with self.assertRaises(WorkbookError): store_workbook(self.user, self.organization, SimpleUploadedFile("contacts.xls", b"bad"))
        uploaded = self.upload([("Sheet1", [["Mobile"], ["1234567890"]])])
        with self.assertRaises(WorkbookError): preview(uploaded["token"], self.user, self.organization, "Sheet1", {"whatsapp_number": "Mobile"}, self.unknown.id, False)
