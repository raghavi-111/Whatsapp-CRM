import logging

from celery import shared_task

from .models import BroadcastCampaign
from .services import send_campaign_now


logger = logging.getLogger(__name__)


@shared_task(bind=True, name="broadcasts.send_scheduled_campaign")
def send_scheduled_campaign(self, campaign_id):
    campaign = BroadcastCampaign.objects.filter(id=campaign_id).first()
    if campaign is None:
        logger.warning("Skipping scheduled broadcast because campaign was not found id=%s", campaign_id)
        return {"status": "skipped", "reason": "campaign_not_found"}
    if campaign.status != BroadcastCampaign.STATUS_SCHEDULED:
        logger.info("Skipping scheduled broadcast id=%s status=%s", campaign.id, campaign.status)
        return {"status": "skipped", "reason": "status_changed"}
    send_campaign_now(campaign)
    return {"status": "completed"}
