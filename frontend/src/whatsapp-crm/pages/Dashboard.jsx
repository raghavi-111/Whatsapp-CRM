import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { BadgeIndianRupee, ChevronRight, Handshake, Inbox, Megaphone, MessageCircle, Send, UserPlus, UserRound, Workflow } from "lucide-react";

import { getAnalyticsSummary, getMessagesAnalytics } from "../services/analyticsService.js";
import { getConversations } from "../services/conversationService.js";
import { getDeals } from "../services/pipelineService.js";
import { clearTokens } from "../../shared/services/tokenStorage.js";

const metricCards = [
  { key: "open_conversations", label: "Active Conversations", icon: MessageCircle, tone: "blue" },
  { key: "total_contacts", label: "New Contacts", icon: UserPlus, tone: "green" },
  { key: "open_deals_value", label: "Open Deals Value", icon: BadgeIndianRupee, tone: "purple", currency: true },
  { key: "outbound_messages_today", label: "Messages Sent", icon: Send, tone: "orange" },
];

const quickActions = [
  { label: "New contact", subtitle: "Add customer details", to: "/contacts", icon: UserPlus },
  { label: "New deal", subtitle: "Create opportunity", to: "/pipelines", icon: Handshake },
  { label: "Broadcast", subtitle: "Message a segment", to: "/broadcasts", icon: Megaphone },
  { label: "Automation", subtitle: "Build a workflow", to: "/automations/new", icon: Workflow },
];

const rangeLabels = { 7: "Last 7 days", 30: "Last 30 days", 90: "Last 90 days" };
const stageColors = ["#1f5cf0", "#1fb266", "#7d4ff0", "#f59921", "#e34d6f", "#14a6a6"];

function asList(payload) { return Array.isArray(payload) ? payload : payload?.results || []; }
function formatNumber(value) { return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 }); }
function formatMoney(value) { return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value || 0)); }
function initials() { return <UserRound aria-hidden="true" size={17} />; }
function firstName(user) { return (user?.name || user?.full_name || user?.email?.split("@")[0] || "there").split(/[\s._-]/)[0]; }
function greeting() { const hour = new Date().getHours(); return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"; }
function relativeTime(value) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "now"; if (seconds < 3600) return `${Math.floor(seconds / 60)}m`; if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`; return `${Math.floor(seconds / 86400)}d`;
}

function buildDealSummary(deals) {
  const stages = [...new Set(deals.map((deal) => deal.stage).filter(Boolean))];
  const openDeals = deals.filter((deal) => deal.status === "open");
  return {
    open_deals_count: openDeals.length,
    open_deals_value: openDeals.reduce((sum, deal) => sum + Number(deal.value || 0), 0),
    pipeline_value_by_stage: stages.map((stage) => ({ stage, count: openDeals.filter((deal) => deal.stage === stage).length, value: openDeals.filter((deal) => deal.stage === stage).reduce((sum, deal) => sum + Number(deal.value || 0), 0) })),
  };
}

function MetricCard({ metric, value, openDealCount }) {
  const Icon = metric.icon;
  return <article className="crm-metric-card"><div className={`metric-icon metric-icon--${metric.tone}`}><Icon size={18} /></div><span>{metric.label}</span><strong>{metric.currency ? formatMoney(value) : formatNumber(value)}</strong><div className="metric-comparison"><small>No change</small><span>{metric.currency ? `${openDealCount || 0} open deals` : "current period"}</span></div></article>;
}

function ActivityChart({ data, range }) {
  const visible = range === 90 ? data.filter((_, index) => index % 6 === 0 || index === data.length - 1) : range === 30 ? data.filter((_, index) => index % 4 === 0 || index === data.length - 1) : data;
  const max = Math.max(1, ...visible.flatMap((item) => [item.inbound || 0, item.outbound || 0]));
  const points = (key) => visible.map((item, index) => `${(index / Math.max(1, visible.length - 1)) * 100},${92 - ((item[key] || 0) / max) * 82}`).join(" ");
  return <div className="activity-chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`Inbound and outbound messages for ${range} days`}><g className="chart-grid-lines"><line x1="0" x2="100" y1="10" y2="10"/><line x1="0" x2="100" y1="37" y2="37"/><line x1="0" x2="100" y1="64" y2="64"/><line x1="0" x2="100" y1="92" y2="92"/></g><polyline className="chart-line chart-line--inbound" points={points("inbound")} /><polyline className="chart-line chart-line--outbound" points={points("outbound")} /></svg><div className="activity-chart__labels">{visible.map((item) => <span key={item.date}>{new Date(`${item.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>)}</div></div>;
}

function Dashboard() {
  const navigate = useNavigate();
  const { user } = useOutletContext();
  const [summary, setSummary] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationRange, setConversationRange] = useState(30);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activityLoading, setActivityLoading] = useState(true);
  const [error, setError] = useState("");
  const [conversationError, setConversationError] = useState("");

  useEffect(() => {
    let mounted = true;
    Promise.all([getAnalyticsSummary(), getDeals(), getConversations()]).then(([analytics, dealsPayload, conversationPayload]) => {
      if (!mounted) return;
      const deals = asList(dealsPayload); setSummary({ ...analytics, ...buildDealSummary(deals) }); setConversations(asList(conversationPayload).slice(0, 4));
    }).catch((requestError) => { if (requestError.response?.status === 401) { clearTokens(); navigate("/login", { replace: true }); } else if (mounted) setError("Unable to load dashboard data."); }).finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, [navigate]);

  useEffect(() => {
    let mounted = true; setActivityLoading(true); setConversationError("");
    getMessagesAnalytics(conversationRange).then((data) => mounted && setActivity(data.daily_by_direction || data.daily_range || [])).catch((requestError) => { if (requestError.response?.status === 401) { clearTokens(); navigate("/login", { replace: true }); } else if (mounted) { setConversationError("Unable to load conversation analytics."); setActivity([]); } }).finally(() => mounted && setActivityLoading(false));
    return () => { mounted = false; };
  }, [conversationRange, navigate]);

  const hasActivity = activity.some((item) => (item.inbound || 0) + (item.outbound || 0) > 0);
  const maxStageValue = useMemo(() => Math.max(1, ...(summary?.pipeline_value_by_stage || []).map((item) => item.value || item.count || 0)), [summary]);

  return <main className="dashboard-page dashboard-page--crm">
    <header className="crm-dashboard-header"><div><h1>{greeting()}, {firstName(user)} <span aria-hidden="true">👋</span></h1><p>Here&apos;s what&apos;s happening with your customers today.</p></div><select aria-label="Dashboard date range" value={conversationRange} onChange={(event) => setConversationRange(Number(event.target.value))}>{Object.entries(rangeLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></header>
    {error && <p className="form-error" role="alert">{error}</p>}
    {loading ? <div className="crm-loading-card">Loading dashboard summary...</div> : summary && <section className="crm-metrics-grid" aria-label="Dashboard metrics">{metricCards.map((metric) => <MetricCard key={metric.key} metric={metric} value={summary[metric.key]} openDealCount={summary.open_deals_count} />)}</section>}
    <section className="crm-dashboard-grid crm-dashboard-grid--analytics">
      <article className="crm-panel activity-panel"><div className="crm-panel__heading"><div><h2>Conversation activity</h2><p>Inbound and outbound message volume</p></div><div className="chart-legend"><span><i className="legend-inbound"/>Inbound</span><span><i className="legend-outbound"/>Outbound</span></div></div>{activityLoading ? <p className="dashboard-loading">Loading conversation analytics...</p> : conversationError ? <p className="form-error">{conversationError}</p> : hasActivity ? <ActivityChart data={activity} range={conversationRange} /> : <div className="crm-empty"><Inbox size={20}/><strong>No message activity in this range</strong><span>Activity will appear as customers send and receive messages.</span></div>}</article>
      <article className="crm-panel quick-actions-panel"><div className="crm-panel__heading"><div><h2>Quick actions</h2><p>Jump into common CRM workflows</p></div></div><div className="quick-actions-list">{quickActions.map(({ label, subtitle, to, icon: Icon }) => <Link to={to} key={to} className="quick-action-row"><span className="quick-action-icon"><Icon size={16}/></span><span><strong>{label}</strong><small>{subtitle}</small></span><ChevronRight size={16}/></Link>)}</div></article>
    </section>
    <section className="crm-dashboard-grid crm-dashboard-grid--bottom">
      <article className="crm-panel pipeline-panel"><div className="crm-panel__heading"><div><h2>Pipeline overview</h2><p>Open deals by stage</p></div></div>{(summary?.pipeline_value_by_stage || []).length ? <div className="pipeline-list">{summary.pipeline_value_by_stage.map((item, index) => <div className="pipeline-row" key={item.stage}><div><strong>{item.stage}</strong><span>{formatMoney(item.value)}</span><small>{item.count} {item.count === 1 ? "deal" : "deals"}</small></div><div className="pipeline-track"><i style={{ width: `${Math.max(item.count || item.value ? 5 : 0, ((item.value || item.count) / maxStageValue) * 100)}%`, background: stageColors[index % stageColors.length] }} /></div></div>)}</div> : <div className="crm-empty"><strong>No pipeline stages yet</strong><span>Create a deal to populate the pipeline overview.</span></div>}</article>
      <article className="crm-panel recent-panel"><div className="crm-panel__heading"><div><h2>Recent conversations</h2><p>Latest customer interactions</p></div></div>{loading ? <p className="dashboard-loading">Loading conversations...</p> : conversationError ? <p className="form-error">{conversationError}</p> : conversations.length ? <div className="recent-list">{conversations.map((conversation) => { const name = conversation.contact_name || conversation.contact_phone || "Unknown contact"; return <Link to={`/inbox?conversation=${conversation.id}`} className="recent-row" key={conversation.id}><span className="recent-avatar">{initials(name)}</span><span className="recent-copy"><strong>{name}</strong><small>{conversation.last_message_preview || "No messages yet"}</small></span><time dateTime={conversation.last_message_at || conversation.updated_at}>{relativeTime(conversation.last_message_at || conversation.updated_at)}</time><span className={`conversation-status conversation-status--${conversation.status}`}>{conversation.status || "open"}</span></Link>; })}</div> : <div className="crm-empty"><MessageCircle size={20}/><strong>No conversations yet</strong><span>New customer conversations will show up here.</span></div>}</article>
    </section>
    <p className="crm-updated">Updated just now <span>•</span> Live data from WhatsApp CRM</p>
  </main>;
}

export default Dashboard;
