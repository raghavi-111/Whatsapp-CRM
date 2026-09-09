from decimal import Decimal

from django.db import models
from django.db.models import Q

from contacts.models import Contact
from organizations.models import Organization


class Deal(models.Model):
    STAGE_NEW = "New"
    STAGE_QUALIFIED = "Qualified"
    STAGE_PROPOSAL = "Proposal"
    STAGE_WON = "Won"

    STAGE_CHOICES = [
        (STAGE_NEW, "New"),
        (STAGE_QUALIFIED, "Qualified"),
        (STAGE_PROPOSAL, "Proposal"),
        (STAGE_WON, "Won"),
    ]

    STATUS_OPEN = "open"
    STATUS_WON = "won"
    STATUS_LOST = "lost"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_WON, "Won"),
        (STATUS_LOST, "Lost"),
    ]

    SOURCE_MANUAL = "manual"
    SOURCE_WHATSAPP = "whatsapp"

    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_WHATSAPP, "WhatsApp"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="deals")
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    title = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_NEW)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "contact"],
                condition=Q(status="open", contact__isnull=False),
                name="unique_open_deal_per_contact_per_org",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "stage"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return self.title
