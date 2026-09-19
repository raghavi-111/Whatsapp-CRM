export default function CampaignStatusBadge({ status }) { return <span className={`email-status email-status--${status.toLowerCase()}`}>{status}</span>; }
