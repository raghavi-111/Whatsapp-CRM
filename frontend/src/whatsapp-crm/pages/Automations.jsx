import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Copy, FileText, Pencil, Plus, Save, Trash2 } from "lucide-react";

import {
  createAutomation,
  deleteAutomation,
  getAutomationLogs,
  getAutomations,
  simulateInboundMessage,
  updateAutomation,
} from "../services/automationService.js";
import { getConversations } from "../services/conversationService.js";
import { clearTokens } from "../../shared/services/tokenStorage.js";

/**
 * Automations Page
 *
 * Route-level rules workspace for creating, editing, duplicating, simulating,
 * and reviewing WhatsApp CRM automation rules.
 */

const conditionExample = `[
  {
    "field": "message_text_contains",
    "operator": "contains",
    "value": "price"
  }
]`;

const actionExample = `[
  {
    "type": "add_tag",
    "tag_name": "Price Enquiry"
  },
  {
    "type": "update_conversation_status",
    "status": "pending"
  },
  {
    "type": "send_message",
    "text": "Thank you for your enquiry. Our sales team will contact you shortly."
  }
]`;

const emptyForm = {
  name: "",
  description: "",
  trigger_type: "inbound_message_received",
  condition_logic: "and",
  conditions_json: conditionExample,
  actions_json: actionExample,
  is_active: true,
};

const defaultLogsPageSize = 5;

const triggers = [
  ["inbound_message_received", "Inbound message received"],
  ["conversation_created", "Conversation created"],
  ["contact_created", "Contact created"],
  ["tag_added", "Tag added"],
  ["conversation_status_changed", "Conversation status changed"],
  ["deal_created", "Deal created"],
  ["deal_stage_changed", "Deal stage changed"],
  ["broadcast_completed", "Broadcast completed"],
];

const quickStartTemplates = [
  {
    id: "welcome-message",
    name: "Welcome Message",
    description: "Auto-reply to first-time contacts with a greeting.",
    badge: "Auto Reply",
    trigger_type: "inbound_message_received",
    condition_logic: "and",
    conditions_json: [{ field: "first_message", operator: "is", value: true }],
    actions_json: [{ type: "send_message", text: "Welcome! Thanks for messaging us. How can we help?" }],
  },
  {
    id: "out-of-office",
    name: "Out of Office",
    description: "Reply during off-hours so nobody is left waiting.",
    badge: "Business Hours",
    trigger_type: "inbound_message_received",
    condition_logic: "and",
    conditions_json: [{ field: "business_hours", operator: "outside", value: "" }],
    actions_json: [{ type: "send_message", text: "Thanks for your message. We are currently offline and will reply soon." }],
  },
  {
    id: "lead-qualifier",
    name: "Lead Qualifier",
    description: "Capture pricing or demo intent and route qualified leads.",
    badge: "Lead Capture",
    trigger_type: "inbound_message_received",
    condition_logic: "or",
    conditions_json: [
      { field: "message_text_contains", operator: "icontains", value: "price" },
      { field: "message_text_contains", operator: "icontains", value: "demo" },
      { field: "message_text_contains", operator: "icontains", value: "plan" },
      { field: "message_text_contains", operator: "icontains", value: "cost" },
    ],
    actions_json: [
      { type: "add_tag", tag_name: "Price Enquiry" },
      { type: "create_deal", stage: "New" },
      { type: "send_message", text: "Thanks for your interest. Could you share your budget and preferred timeline?" },
      { type: "create_notification", message: "New pricing or demo enquiry received." },
    ],
  },
  {
    id: "follow-up-reminder",
    name: "Follow-up Reminder",
    description: "Nudge the team when a contact needs a follow-up.",
    badge: "Reminder",
    trigger_type: "conversation_status_changed",
    condition_logic: "and",
    conditions_json: [{ field: "conversation_status", operator: "equals", value: "pending" }],
    actions_json: [
      { type: "add_contact_note", note: "Follow up with this contact within 24 hours." },
      { type: "create_notification", message: "Follow-up reminder: contact needs attention." },
    ],
  },
];

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function parseJsonField(value, label) {
  try {
    const parsed = JSON.parse(value || "[]");
    if (!Array.isArray(parsed)) {
      throw new Error(`${label} must be a JSON array.`);
    }
    return parsed;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(`${label} JSON is invalid.`);
    }
    throw new Error(error.message || `${label} JSON is invalid.`);
  }
}

function formatBackendError(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.join(" ");

  const fieldLabels = {
    name: "Name",
    trigger_type: "Trigger",
    conditions_json: "Conditions JSON",
    actions_json: "Actions JSON",
    detail: "Error",
    non_field_errors: "Error",
  };

  return Object.entries(data)
    .map(([field, value]) => {
      const label = fieldLabels[field] || field;
      const message = Array.isArray(value)
        ? value.join(" ")
        : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
      return `${label}: ${message}`;
    })
    .join(" ");
}

function Automations() {
  const navigate = useNavigate();

  // Automation rules, execution logs, and conversation options used by forms.
  const [rules, setRules] = useState([]);
  const [logs, setLogs] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [formData, setFormData] = useState(emptyForm);
  const [simulationForm, setSimulationForm] = useState({ conversation_id: "", text: "what is the price?" });
  const [editingRuleId, setEditingRuleId] = useState(null);
  const [logsPage, setLogsPage] = useState(1);
  const [logsPageSize, setLogsPageSize] = useState(defaultLogsPageSize);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadPageData();
  }, []);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(logs.length / logsPageSize));
    setLogsPage((currentPage) => Math.min(currentPage, totalPages));
  }, [logs.length, logsPageSize]);

  async function loadPageData() {
    setIsLoading(true);
    setError("");

    try {
      const [rulesData, logsData, conversationData] = await Promise.all([
        getAutomations(),
        getAutomationLogs(),
        getConversations({ ordering: "-last_message_at" }),
      ]);
      setRules(rulesData);
      setLogs(logsData);
      setConversations(conversationData);
      setSimulationForm((current) => ({
        ...current,
        conversation_id: current.conversation_id || conversationData[0]?.id || "",
      }));
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        clearTokens();
        navigate("/login", { replace: true });
        return;
      }
      setError("Unable to load automations.");
    } finally {
      setIsLoading(false);
    }
  }

  function updateFormField(event) {
    const { name, type, checked, value } = event.target;
    setFormData((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  function updateSimulationField(event) {
    setSimulationForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function resetForm() {
    setEditingRuleId(null);
    setFormData(emptyForm);
  }

  function startEdit(rule) {
    setEditingRuleId(rule.id);
    setFormData({
      name: rule.name || "",
      description: rule.description || "",
      trigger_type: rule.trigger_type || "inbound_message_received",
      condition_logic: rule.condition_logic || "and",
      conditions_json: JSON.stringify(rule.conditions_json || [], null, 2),
      actions_json: JSON.stringify(rule.actions_json || [], null, 2),
      is_active: Boolean(rule.is_active),
    });
    setError("");
    setMessage("");
  }

  function getRuleLogs(rule) {
    return logs.filter((log) => {
      const logRuleId = log.rule_id || log.rule?.id || log.rule;
      return String(logRuleId) === String(rule.id);
    });
  }

  function openLogs() {
    setLogsPage(1);
  }

  function openTemplateBuilder(template) {
    setError("");
    setMessage("");
    navigate("/automations/new", { state: { template } });
  }

  async function toggleRule(rule) {
    setError("");
    setMessage("");

    try {
      await updateAutomation(rule.id, { is_active: !rule.is_active });
      setMessage(rule.is_active ? "Automation paused." : "Automation activated.");
      await loadPageData();
    } catch (requestError) {
      setError(formatBackendError(requestError.response?.data) || "Unable to update automation.");
    }
  }

  async function duplicateRule(rule) {
    setError("");
    setMessage("");

    try {
      await createAutomation({
        name: `${rule.name} copy`,
        description: rule.description || "",
        trigger_type: rule.trigger_type,
        condition_logic: rule.condition_logic || "and",
        conditions_json: rule.conditions_json || [],
        actions_json: rule.actions_json || [],
        is_active: false,
      });
      setMessage("Automation duplicated.");
      await loadPageData();
    } catch (requestError) {
      setError(formatBackendError(requestError.response?.data) || "Unable to duplicate automation.");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        trigger_type: formData.trigger_type,
        condition_logic: formData.condition_logic,
        conditions_json: parseJsonField(formData.conditions_json, "Conditions"),
        actions_json: parseJsonField(formData.actions_json, "Actions"),
        is_active: formData.is_active,
      };

      if (editingRuleId) {
        await updateAutomation(editingRuleId, payload);
        setMessage("Automation updated.");
      } else {
        await createAutomation(payload);
        setMessage("Automation created.");
      }

      resetForm();
      await loadPageData();
    } catch (requestError) {
      setError(formatBackendError(requestError.response?.data) || requestError.message || "Unable to save automation.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(rule) {
    const confirmed = window.confirm(`Delete automation ${rule.name}?`);
    if (!confirmed) return;

    setError("");
    setMessage("");

    try {
      await deleteAutomation(rule.id);
      setMessage("Automation deleted.");
      await loadPageData();
    } catch {
      setError("Unable to delete automation.");
    }
  }

  async function handleSimulation(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      await simulateInboundMessage({
        conversation_id: Number(simulationForm.conversation_id),
        text: simulationForm.text,
      });
      setMessage("Inbound message simulated. Automation logs may refresh after the background task completes.");
      await loadPageData();
    } catch (requestError) {
      setError(formatBackendError(requestError.response?.data) || "Unable to simulate inbound message.");
    } finally {
      setIsSaving(false);
    }
  }

  const logsTotalPages = Math.max(1, Math.ceil(logs.length / logsPageSize));
  const logsStartIndex = (logsPage - 1) * logsPageSize;
  const visibleLogs = logs.slice(logsStartIndex, logsStartIndex + logsPageSize);

  return (
    <section className="dashboard-page automations-page">
      <div className="dashboard-header automations-page__header">
        <div>
          <h1>Automations</h1>
          <p>Build workflows that react to WhatsApp events automatically.</p>
        </div>
        <Link className="button button--primary" to="/automations/new">
          <Plus size={16} aria-hidden="true" />
          Create automation
        </Link>
      </div>

      <section className="quick-template-section">
        <h2>Quick-start templates</h2>
        <div className="quick-template-grid">
          {quickStartTemplates.map((template) => (
            <button
              className="template-card"
              disabled={isSaving}
              key={template.name}
              onClick={() => openTemplateBuilder(template)}
              type="button"
            >
              <span className="template-card__badge">{template.badge}</span>
              <strong>{template.name}</strong>
              <span>{template.description}</span>
              <small>Customize</small>
            </button>
          ))}
        </div>
      </section>

      {editingRuleId ? (
        <form className="panel contact-form automation-form" onSubmit={handleSubmit}>
        <h2>{editingRuleId ? "Edit automation" : "Create automation"}</h2>

        <div className="form-grid">
          <label>
            Name
            <input name="name" onChange={updateFormField} required type="text" value={formData.name} />
          </label>
          <label>
            Trigger
            <select name="trigger_type" onChange={updateFormField} value={formData.trigger_type}>
              {triggers.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Condition logic
            <select name="condition_logic" onChange={updateFormField} value={formData.condition_logic}>
              <option value="and">All conditions (AND)</option>
              <option value="or">Any condition (OR)</option>
            </select>
          </label>
        </div>

        <label>
          Description
          <textarea name="description" onChange={updateFormField} rows="2" value={formData.description} />
        </label>

        <label className="checkbox-label">
          <input checked={formData.is_active} name="is_active" onChange={updateFormField} type="checkbox" />
          Active
        </label>

        <div className="json-help-grid">
          <label>
            Conditions JSON
            <textarea
              name="conditions_json"
              onChange={updateFormField}
              required
              rows="7"
              value={formData.conditions_json}
            />
          </label>
          <label>
            Actions JSON
            <textarea
              name="actions_json"
              onChange={updateFormField}
              required
              rows="7"
              value={formData.actions_json}
            />
          </label>
        </div>

        <div className="help-text">
          <p>Example condition:</p>
          <pre>{conditionExample}</pre>
          <p>Example action:</p>
          <pre>{actionExample}</pre>
        </div>

        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <div className="actions">
          <button className="button button--primary" disabled={isSaving} type="submit">
            <Save size={16} aria-hidden="true" />
            {isSaving ? "Saving..." : editingRuleId ? "Update Automation" : "Create Automation"}
          </button>
          {editingRuleId ? (
            <button className="button" onClick={resetForm} type="button">
              Cancel
            </button>
          ) : null}
        </div>
        </form>
      ) : null}

      <div className="contacts-panel">
        <div className="automation-rules-heading">
          <div>
            <h2>Automation rules</h2>
            <p>Only saved automation rules from your workspace appear here.</p>
          </div>
        </div>
        {isLoading ? <p>Loading automations...</p> : null}
        {!isLoading && rules.length === 0 ? (
          <div className="panel empty-state">
            <strong>No automation rules yet</strong>
            <span>No automation rules yet. Create one from scratch or customize a quick-start template.</span>
          </div>
        ) : null}
        {!isLoading && rules.length > 0 ? (
          <div className="list-grid automation-rules-grid">
            {rules.map((rule) => {
              const ruleLogs = getRuleLogs(rule);
              const latestRun = ruleLogs[0]?.created_at;
              return (
                <article className="automation-card" key={rule.id}>
                  <header className="automation-card__header">
                    <h2>{rule.name}</h2>
                    <label className="switch">
                      <input checked={Boolean(rule.is_active)} onChange={() => toggleRule(rule)} type="checkbox" />
                      <span />
                    </label>
                  </header>

                  <p className="automation-card__description">{rule.description || "No description yet."}</p>

                  <div className="automation-card__trigger">
                    <span className="badge automation-card__trigger-badge" title={rule.trigger_type}>
                      {rule.trigger_type}
                    </span>
                    <span className="badge automation-card__trigger-badge" title="Condition logic">
                      {(rule.condition_logic || "and").toUpperCase()}
                    </span>
                  </div>

                  <dl className="automation-card__stats">
                    <div>
                      <dt>Runs</dt>
                      <dd>{ruleLogs.length}</dd>
                    </div>
                    <div>
                      <dt>Last run</dt>
                      <dd>{latestRun ? formatDate(latestRun) : "No runs yet"}</dd>
                    </div>
                  </dl>

                  <footer className="automation-actions">
                    <button className="button button--small" onClick={() => startEdit(rule)} type="button">
                      <Pencil size={14} aria-hidden="true" />
                      Edit
                    </button>
                    <button className="button button--small" onClick={() => duplicateRule(rule)} type="button">
                      <Copy size={14} aria-hidden="true" />
                      Duplicate
                    </button>
                    <a className="button button--small" href="#automation-logs" onClick={openLogs}>
                      <FileText size={14} aria-hidden="true" />
                      Logs
                    </a>
                    <button className="button button--small" onClick={() => handleDelete(rule)} type="button">
                      <Trash2 size={14} aria-hidden="true" />
                      Delete
                    </button>
                  </footer>
                </article>
              );
            })}
          </div>
        ) : null}
      </div>

      <section className="automations-bottom-grid">
      <form className="panel contact-form automation-form automation-test-panel" onSubmit={handleSimulation}>
        <h2>Developer inbound test</h2>
        <div className="form-grid">
          <label>
            Contact / conversation
            <select
              name="conversation_id"
              onChange={updateSimulationField}
              required
              value={simulationForm.conversation_id}
            >
              {conversations.length === 0 ? <option value="">No conversations available</option> : null}
              {conversations.map((conversation) => (
                <option key={conversation.id} value={conversation.id}>
                  {conversation.contact_name || conversation.contact_phone} - {conversation.contact_phone}
                </option>
              ))}
            </select>
          </label>
          <label>
            Inbound message text
            <input
              name="text"
              onChange={updateSimulationField}
              required
              type="text"
              value={simulationForm.text}
            />
          </label>
        </div>
        <button
          className="button button--primary"
          disabled={isSaving || !simulationForm.conversation_id}
          type="submit"
        >
          {isSaving ? "Simulating..." : "Simulate Inbound Message"}
        </button>
      </form>

      <div className="panel contacts-panel automation-latest-panel" id="automation-logs">
        <h2>Latest logs</h2>
        {logs.length === 0 ? <p>No automation logs yet.</p> : null}
        {logs.length > 0 ? (
          <>
            <div className="automation-log-list">{visibleLogs.map((log) => <div className="automation-log-row" key={log.id}><span className={`automation-log-status automation-log-status--${log.status}`}>{titleizeStatus(log.status)}</span><p>{log.message || titleizeStatus(log.trigger_type)}</p><time>{formatDate(log.created_at)}</time></div>)}</div>

            <div className="table-pagination">
              <label className="table-pagination__size">
                Rows per page
                <select
                  onChange={(event) => {
                    setLogsPageSize(Number(event.target.value));
                    setLogsPage(1);
                  }}
                  value={logsPageSize}
                >
                  <option value="5">5</option>
                  <option value="10">10</option>
                  <option value="20">20</option>
                </select>
              </label>
              <span className="table-pagination__page">Page {logsPage} of {logsTotalPages}</span>
              <div className="table-pagination__actions">
                <button
                  className="button button--small"
                  disabled={logsPage === 1}
                  onClick={() => setLogsPage((currentPage) => Math.max(1, currentPage - 1))}
                  type="button"
                >
                  Previous
                </button>
                <button
                  className="button button--small"
                  disabled={logsPage === logsTotalPages}
                  onClick={() => setLogsPage((currentPage) => Math.min(logsTotalPages, currentPage + 1))}
                  type="button"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
      </section>
    </section>
  );
}

function titleizeStatus(value) {
  return String(value || "Unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default Automations;
