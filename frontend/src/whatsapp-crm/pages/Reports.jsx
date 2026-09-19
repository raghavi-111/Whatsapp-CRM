import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getAutomationsAnalytics, getConversationsAnalytics, getMessagesAnalytics } from "../services/analyticsService.js";
import { clearTokens } from "../../shared/services/tokenStorage.js";

const conversationColors = { open: "blue", pending: "orange", assigned: "purple", unassigned: "green", resolved: "green" };
const automationColors = { success: "green", skipped: "blue", failed: "red" };

function sumValues(value = {}) { return Object.values(value).reduce((sum, count) => sum + Number(count || 0), 0); }
function titleize(value) { return String(value || "-").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }

function ProgressList({ items, colors }) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return <div className="analytics-progress-list">{items.map((item) => <div className="analytics-progress-row" key={item.label}>
    <div><span>{titleize(item.label)}</span><strong>{item.count}</strong></div>
    <div className="analytics-track"><i className={`analytics-fill analytics-fill--${colors[item.label] || "blue"}`} style={{ width: `${(item.count / max) * 100}%` }} /></div>
  </div>)}</div>;
}

function Reports() {
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const [messages, setMessages] = useState(null);
  const [conversations, setConversations] = useState(null);
  const [automations, setAutomations] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    setIsLoading(true); setError("");
    Promise.all([getMessagesAnalytics(days), getConversationsAnalytics(), getAutomationsAnalytics()])
      .then(([messageData, conversationData, automationData]) => { if (mounted) { setMessages(messageData); setConversations(conversationData); setAutomations(automationData); } })
      .catch((requestError) => { if (requestError.response?.status === 401) { clearTokens(); navigate("/login", { replace: true }); } else if (mounted) setError("Unable to load analytics."); })
      .finally(() => mounted && setIsLoading(false));
    return () => { mounted = false; };
  }, [days, navigate]);

  const messageTotal = sumValues(messages?.by_direction);
  const conversationTotal = sumValues(conversations?.by_status);
  const delivery = messages?.by_delivery_status || {};
  const delivered = Number(delivery.delivered || delivery.read || 0);
  const deliveryRate = messageTotal ? Math.round((delivered / messageTotal) * 100) : 0;
  const automationTotal = sumValues(automations?.by_status);
  const automationSuccess = Number(automations?.by_status?.success || 0);
  const daily = messages?.daily_by_direction || [];
  const chartDays = daily.length > 7 ? daily.filter((_, index) => index % Math.ceil(daily.length / 7) === 0).slice(-7) : daily;
  const chartMax = Math.max(1, ...chartDays.flatMap((row) => [Number(row.inbound || 0), Number(row.outbound || 0)]));
  const conversationItems = useMemo(() => {
    const statusItems = Object.entries(conversations?.by_status || {}).map(([label, count]) => ({ label, count: Number(count || 0) }));
    const assignmentItems = Object.entries(conversations?.assignment || {}).map(([label, count]) => ({ label, count: Number(count || 0) }));
    return [...statusItems, ...assignmentItems].slice(0, 4);
  }, [conversations]);
  const automationItems = Object.entries(automations?.by_status || {}).map(([label, count]) => ({ label, count: Number(count || 0) }));
  const deliveryItems = ["delivered", "sent", "failed"].map((label) => ({ label, count: Number(delivery[label] || 0) }));

  return <section className="dashboard-page analytics-page">
    <header className="dashboard-header analytics-page__header"><div><h1>Analytics</h1><p>Monitor conversations, delivery, automations, and team performance.</p></div><select aria-label="Analytics date range" value={days} onChange={(event) => setDays(Number(event.target.value))}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option></select></header>
    {error ? <p className="form-error">{error}</p> : null}
    {isLoading ? <div className="analytics-loading">Loading analytics...</div> : <>
      <section className="analytics-metrics">
        <article><span>Messages</span><div><strong>{messageTotal}</strong><em className="positive">+18%</em></div></article>
        <article><span>Conversations</span><div><strong>{conversationTotal}</strong><em className="positive">+4%</em></div></article>
        <article><span>Delivery rate</span><div><strong>{deliveryRate}%</strong><em className="negative">-3%</em></div></article>
        <article><span>Automation success</span><div><strong>{automationSuccess}</strong><em className="positive">+9%</em></div></article>
      </section>
      <section className="analytics-primary-grid">
        <article className="analytics-card analytics-volume"><h2>Message volume</h2><p>Inbound and outbound messages</p><div className="analytics-chart">
          {chartDays.map((row, index) => <div className="analytics-chart-group" key={row.date || index}><div><i className="inbound" style={{ height: `${Math.max(5, Number(row.inbound || 0) / chartMax * 100)}%` }} /><i className="outbound" style={{ height: `${Math.max(5, Number(row.outbound || 0) / chartMax * 100)}%` }} /></div><span>{new Date(`${row.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</span></div>)}
          {!chartDays.length ? <span className="analytics-empty">No message activity in this period.</span> : null}
        </div></article>
        <article className="analytics-card"><h2>Delivery status</h2><ProgressList items={deliveryItems} colors={{ delivered: "green", sent: "blue", failed: "red" }} /></article>
      </section>
      <section className="analytics-secondary-grid">
        <article className="analytics-card"><h2>Conversation analytics</h2><ProgressList items={conversationItems} colors={conversationColors} /></article>
        <article className="analytics-card"><h2>Automation analytics</h2><ProgressList items={automationItems} colors={automationColors} />{!automationTotal ? <span className="analytics-empty">No automation activity yet.</span> : null}</article>
      </section>
    </>}
  </section>;
}

export default Reports;
