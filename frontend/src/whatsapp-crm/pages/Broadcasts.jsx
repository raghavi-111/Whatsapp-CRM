import { useEffect, useMemo, useState } from "react";
import { Megaphone, Pencil, Save, Search, Send, X } from "lucide-react";

import {
  cancelBroadcast,
  createBroadcastCampaign,
  estimateBroadcastRecipients,
  getBroadcastCampaigns,
  scheduleBroadcast,
  sendBroadcastNow,
  updateBroadcastCampaign,
} from "../services/broadcastService.js";
import { getTags } from "../services/supportService.js";
import { getTemplates } from "../services/templateService.js";

const audienceTypes = [
  ["all", "All contacts"],
  ["tags", "Contacts by selected tags"],
  ["filters", "Contacts by status/source"],
];

const mappingTypes = [
  ["contact_name", "Contact Name"],
  ["phone_number", "Phone Number"],
  ["company", "Company"],
  ["static", "Static Text"],
];

const emptyForm = {
  name: "",
  audience_type: "all",
  selected_tag_ids: [],
  contact_status: "",
  contact_source: "",
  template: "",
  template_language: "",
  variable_mappings: [],
  scheduled_at: "",
};

function extractTemplateVariables(template) {
  const matches = [...(template?.body_text || "").matchAll(/{{\s*(\d+)\s*}}/g)].map((match) => Number(match[1]));
  const max = Math.max(0, ...matches);
  return Array.from({ length: max }, (_, index) => index + 1);
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function requestErrorMessage(error, fallback) {
  const data = error.response?.data;
  if (data?.detail) return data.detail;
  if (data?.name?.[0]) return data.name[0];
  if (data?.template?.[0]) return data.template[0];
  if (data?.selected_tag_ids?.[0]) return data.selected_tag_ids[0];
  if (data?.variable_mappings?.[0]) return data.variable_mappings[0];
  if (data?.non_field_errors?.[0]) return data.non_field_errors[0];
  return fallback;
}

function renderPreview(template, mappings) {
  if (!template) return "Select an approved template to preview the broadcast message.";
  return (template.body_text || "").replace(/{{\s*(\d+)\s*}}/g, (_, index) => {
    const mapping = mappings[Number(index) - 1];
    if (!mapping) return `{{${index}}}`;
    if (mapping.type === "static") return mapping.value || `{{${index}}}`;
    return `[${mappingTypes.find(([value]) => value === mapping.type)?.[1] || "Value"}]`;
  });
}

function Broadcasts() {
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [tags, setTags] = useState([]);
  const [formData, setFormData] = useState(emptyForm);
  const [editingCampaignId, setEditingCampaignId] = useState(null);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [actionCampaignId, setActionCampaignId] = useState(null);
  const [estimate, setEstimate] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [templateFilter, setTemplateFilter] = useState("");

  useEffect(() => {
    loadBroadcastWorkspace();
  }, []);

  const selectedTemplate = useMemo(
    () => templates.find((template) => String(template.id) === String(formData.template)),
    [templates, formData.template],
  );

  const templateVariables = useMemo(() => extractTemplateVariables(selectedTemplate), [selectedTemplate]);
  const previewText = useMemo(
    () => renderPreview(selectedTemplate, formData.variable_mappings),
    [selectedTemplate, formData.variable_mappings],
  );
  const filteredCampaigns = campaigns.filter((campaign) => (!search || campaign.name?.toLowerCase().includes(search.toLowerCase())) && (!statusFilter || campaign.status === statusFilter) && (!templateFilter || String(campaign.template) === templateFilter));
  const totalRecipients = campaigns.reduce((sum, campaign) => sum + Number(campaign.recipient_count || 0), 0);
  const totalDelivered = campaigns.reduce((sum, campaign) => sum + Number(campaign.delivered_count || 0), 0);
  const totalRead = campaigns.reduce((sum, campaign) => sum + Number(campaign.read_count || 0), 0);

  useEffect(() => {
    if (!isCreating) return;
    loadEstimate();
  }, [formData.audience_type, formData.selected_tag_ids, formData.contact_status, formData.contact_source, isCreating]);

  async function loadBroadcastWorkspace() {
    setIsLoading(true);
    setError("");
    try {
      const [campaignData, templateData, tagData] = await Promise.all([
        getBroadcastCampaigns(),
        getTemplates({ status: "approved" }),
        getTags(),
      ]);
      setCampaigns(campaignData);
      setTemplates(templateData);
      setTags(tagData);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to load broadcasts."));
    } finally {
      setIsLoading(false);
    }
  }

  async function loadEstimate(nextForm = formData) {
    try {
      const data = await estimateBroadcastRecipients({
        audience_type: nextForm.audience_type,
        selected_tag_ids: nextForm.selected_tag_ids.map(Number),
        contact_status: nextForm.contact_status,
        contact_source: nextForm.contact_source,
      });
      setEstimate(data.recipient_count || 0);
    } catch {
      setEstimate(0);
    }
  }

  function updateField(event) {
    const { name, value } = event.target;
    setFormData((current) => {
      const next = { ...current, [name]: value };
      if (name === "template") {
        const template = templates.find((item) => String(item.id) === String(value));
        const variables = extractTemplateVariables(template);
        next.template_language = template?.language || "";
        next.variable_mappings = variables.map(() => ({ type: "contact_name", value: "" }));
      }
      return next;
    });
  }

  function updateTagSelection(event) {
    const selected = Array.from(event.target.selectedOptions, (option) => option.value);
    setFormData((current) => ({ ...current, selected_tag_ids: selected }));
  }

  function updateMapping(index, field, value) {
    setFormData((current) => {
      const mappings = [...current.variable_mappings];
      mappings[index] = { ...mappings[index], [field]: value };
      return { ...current, variable_mappings: mappings };
    });
  }

  function openCreateForm() {
    setFormData(emptyForm);
    setEditingCampaignId(null);
    setSelectedCampaign(null);
    setIsReviewing(false);
    setMessage("");
    setError("");
    setEstimate(0);
    setIsCreating(true);
  }

  function editCampaign(campaign) {
    setFormData({
      name: campaign.name || "",
      audience_type: campaign.audience_type || "all",
      selected_tag_ids: (campaign.selected_tag_ids || []).map(String),
      contact_status: campaign.contact_status || "",
      contact_source: campaign.contact_source || "",
      template: campaign.template ? String(campaign.template) : "",
      template_language: campaign.template_language || "",
      variable_mappings: campaign.variable_mappings || [],
      scheduled_at: campaign.scheduled_at ? campaign.scheduled_at.slice(0, 16) : "",
    });
    setEditingCampaignId(campaign.id);
    setSelectedCampaign(null);
    setIsReviewing(false);
    setError("");
    setMessage("");
    setEstimate(campaign.recipient_count || 0);
    setIsCreating(true);
  }

  function closeForm() {
    setIsCreating(false);
    setIsReviewing(false);
    setEditingCampaignId(null);
    setFormData(emptyForm);
    setError("");
  }

  function buildPayload() {
    return {
      name: formData.name,
      audience_type: formData.audience_type,
      selected_tag_ids: formData.selected_tag_ids.map(Number),
      contact_status: formData.audience_type === "filters" ? formData.contact_status : "",
      contact_source: formData.audience_type === "filters" ? formData.contact_source : "",
      template: Number(formData.template),
      template_language: formData.template_language,
      variable_mappings: formData.variable_mappings,
    };
  }

  async function saveDraft(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");
    try {
      if (editingCampaignId) {
        await updateBroadcastCampaign(editingCampaignId, buildPayload());
        setMessage("Broadcast draft updated.");
      } else {
        await createBroadcastCampaign(buildPayload());
        setMessage("Broadcast draft saved.");
      }
      closeForm();
      await loadBroadcastWorkspace();
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to save broadcast draft."));
    } finally {
      setIsSaving(false);
    }
  }

  async function createThenAct(action) {
    setIsSaving(true);
    setError("");
    setMessage("");
    try {
      const campaign = editingCampaignId
        ? await updateBroadcastCampaign(editingCampaignId, buildPayload())
        : await createBroadcastCampaign(buildPayload());
      if (action === "send") {
        await sendBroadcastNow(campaign.id);
        setMessage("Broadcast sent.");
      } else {
        await scheduleBroadcast(campaign.id, new Date(formData.scheduled_at).toISOString());
        setMessage("Broadcast scheduled.");
      }
      closeForm();
      await loadBroadcastWorkspace();
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to run broadcast action."));
    } finally {
      setIsSaving(false);
    }
  }

  async function runCampaignAction(campaign, action) {
    setActionCampaignId(campaign.id);
    setError("");
    setMessage("");
    try {
      if (action === "send") {
        await sendBroadcastNow(campaign.id);
        setMessage("Broadcast sent.");
      } else {
        await cancelBroadcast(campaign.id);
        setMessage("Broadcast cancelled.");
      }
      await loadBroadcastWorkspace();
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to update broadcast."));
    } finally {
      setActionCampaignId(null);
    }
  }

  return (
    <section className="dashboard-page broadcasts-page">
      <div className="dashboard-header broadcasts-page__header">
        <div>
          <h1>Broadcasts</h1>
          <p>Create template-based WhatsApp campaigns, target audiences, and track delivery.</p>
        </div>
        <button className="button button--primary" onClick={openCreateForm} type="button">
          <Megaphone size={16} aria-hidden="true" />
          Create broadcast
        </button>
      </div>

      {!isCreating && message ? <p className="form-success">{message}</p> : null}
      {!isCreating && error ? <p className="form-error">{error}</p> : null}

      {!isCreating ? <>
        <section className="broadcast-metrics" aria-label="Broadcast summary">
          <article><span>Total campaigns</span><strong>{campaigns.length}</strong></article><article><span>Recipients</span><strong>{totalRecipients}</strong></article><article><span>Delivered</span><strong>{totalDelivered}</strong></article><article><span>Read</span><strong>{totalRead}</strong></article>
        </section>
        <section className="broadcast-filters">
          <label><Search size={14} aria-hidden="true" /><input aria-label="Search campaigns" onChange={(event) => setSearch(event.target.value)} placeholder="Search campaigns" value={search} /></label>
          <select aria-label="Filter by status" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="">All statuses</option>{[...new Set(campaigns.map((campaign) => campaign.status))].map((status) => <option key={status} value={status}>{status}</option>)}</select>
          <select aria-label="Filter by template" onChange={(event) => setTemplateFilter(event.target.value)} value={templateFilter}><option value="">All templates</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select>
          <select aria-label="Date range" defaultValue="range"><option value="7">Last 7 days</option><option value="range">Date range</option><option value="90">Last 90 days</option></select>
        </section>
      </> : null}

      {isCreating ? (
        <form className="panel contact-form broadcast-form" onSubmit={saveDraft}>
          <div className="contact-form__header">
            <h2>{editingCampaignId ? "Edit broadcast draft" : "New broadcast"}</h2>
            <button aria-label="Close broadcast form" className="icon-button" onClick={closeForm} type="button">
              <X size={16} aria-hidden="true" />
            </button>
          </div>

          <div className="form-grid">
            <label>
              Campaign name
              <input name="name" onChange={updateField} required type="text" value={formData.name} />
            </label>
            <label>
              Audience
              <select name="audience_type" onChange={updateField} value={formData.audience_type}>
                {audienceTypes.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            {formData.audience_type === "tags" ? (
              <label>
                Tags
                <select multiple onChange={updateTagSelection} value={formData.selected_tag_ids}>
                  {tags.map((tag) => (
                    <option key={tag.id} value={tag.id}>{tag.name}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {formData.audience_type === "filters" ? (
              <>
                <label>
                  Contact status
                  <select name="contact_status" onChange={updateField} value={formData.contact_status}>
                    <option value="">Any status</option>
                    <option value="new">New</option>
                    <option value="active">Active</option>
                    <option value="blocked">Blocked</option>
                  </select>
                </label>
                <label>
                  Contact source
                  <select name="contact_source" onChange={updateField} value={formData.contact_source}>
                    <option value="">Any source</option>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="manual">Manual</option>
                    <option value="import">Import</option>
                    <option value="website">Website</option>
                  </select>
                </label>
              </>
            ) : null}
            <label>
              Approved template
              <select name="template" onChange={updateField} required value={formData.template}>
                <option value="">Select template</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.language}) - {template.category}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Template language
              <input name="template_language" onChange={updateField} required type="text" value={formData.template_language} />
            </label>
          </div>

          {selectedTemplate ? (
            <div className="broadcast-template-preview">
              <strong>{selectedTemplate.name}</strong>
              <span>{selectedTemplate.category} / {selectedTemplate.language}</span>
              <p>{selectedTemplate.body_text}</p>
            </div>
          ) : null}

          {templateVariables.length > 0 ? (
            <div className="broadcast-variable-grid">
              {templateVariables.map((variable, index) => (
                <div className="broadcast-variable-row" key={variable}>
                  <strong>{`{{${variable}}}`}</strong>
                  <select
                    onChange={(event) => updateMapping(index, "type", event.target.value)}
                    value={formData.variable_mappings[index]?.type || "contact_name"}
                  >
                    {mappingTypes.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  {formData.variable_mappings[index]?.type === "static" ? (
                    <input
                      onChange={(event) => updateMapping(index, "value", event.target.value)}
                      placeholder="Static text"
                      type="text"
                      value={formData.variable_mappings[index]?.value || ""}
                    />
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}

          <div className="broadcast-review-panel">
            <div>
              <strong>Estimated recipients</strong>
              <span>{estimate}</span>
            </div>
            <div>
              <strong>Preview</strong>
              <p>{previewText}</p>
            </div>
          </div>

          <label>
            Schedule time
            <input name="scheduled_at" onChange={updateField} type="datetime-local" value={formData.scheduled_at} />
          </label>

          {isReviewing ? (
            <div className="form-success">
              Review ready. Confirm the approved template, audience estimate, and preview before sending.
            </div>
          ) : null}
          {error ? <p className="form-error">{error}</p> : null}

          <div className="actions">
            <button className="button button--primary" disabled={isSaving} type="submit">
              <Save size={16} aria-hidden="true" />
              {isSaving ? "Saving..." : "Save Draft"}
            </button>
            <button className="button" disabled={isSaving} onClick={() => setIsReviewing(true)} type="button">
              Review
            </button>
            <button className="button" disabled={isSaving} onClick={() => createThenAct("send")} type="button">
              <Send size={16} aria-hidden="true" />
              Send Now
            </button>
            <button className="button" disabled={isSaving || !formData.scheduled_at} onClick={() => createThenAct("schedule")} type="button">
              Schedule
            </button>
            <button className="button" disabled={isSaving} onClick={closeForm} type="button">
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      <div className="panel contacts-panel">
        {isLoading ? <p className="dashboard-loading">Loading broadcasts...</p> : null}
        {!isLoading && campaigns.length === 0 ? (
          <div className="empty-state">
            <strong>No broadcasts yet</strong>
            <span>Create a broadcast draft to prepare customer updates or announcements.</span>
          </div>
        ) : null}
        {!isLoading && campaigns.length > 0 ? (
          <div className="table-wrap contacts-table-scroll">
            <table className="contacts-table broadcast-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Template</th>
                  <th>Audience</th>
                  <th>Status</th>
                  <th>Scheduled</th>
                  <th>Delivery</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCampaigns.map((campaign) => (
                  <tr key={campaign.id}>
                    <td>
                      <span className="broadcast-table__text">{campaign.name}</span>
                    </td>
                    <td>
                      <span className="broadcast-table__text">{campaign.template_name || "-"}</span>
                    </td>
                    <td>
                      <span className="broadcast-table__meta">{campaign.audience_summary}</span>
                    </td>
                    <td><span className={`pill pill--${campaign.status}`}>{campaign.status}</span></td>
                    <td>
                      <span className="broadcast-table__meta">{formatDate(campaign.scheduled_at)}</span>
                    </td>
                    <td>
                      <span className="broadcast-counts">
                        <span className="broadcast-delivery-summary">{campaign.sent_count} sent · {campaign.read_count} read</span>
                        <span>{campaign.recipient_count} Recipients</span>
                        <span>{campaign.sent_count} Sent</span>
                        <span>{campaign.delivered_count} Delivered</span>
                        <span>{campaign.read_count} Read</span>
                        <span>{campaign.failed_count} Failed</span>
                      </span>
                    </td>
                    <td>
                      <div className="row-actions broadcast-table__actions">
                        <button className="button button--small" onClick={() => setSelectedCampaign(campaign)} type="button">Details</button>
                        {campaign.status === "draft" ? (
                          <>
                            <button className="button button--small" onClick={() => editCampaign(campaign)} type="button">
                              <Pencil size={14} aria-hidden="true" />
                              Edit Draft
                            </button>
                            <button className="button button--small" disabled={actionCampaignId === campaign.id} onClick={() => runCampaignAction(campaign, "send")} type="button">
                              <Send size={14} aria-hidden="true" />
                              Send Now
                            </button>
                          </>
                        ) : null}
                        {["draft", "scheduled"].includes(campaign.status) ? (
                          <button className="button button--small" disabled={actionCampaignId === campaign.id} onClick={() => runCampaignAction(campaign, "cancel")} type="button">
                            Cancel
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {selectedCampaign ? (
        <div className="deal-modal" role="presentation">
          <div className="contact-modal__scrim" onClick={() => setSelectedCampaign(null)} />
          <section aria-modal="true" className="panel deal-detail-modal broadcast-detail-modal" role="dialog">
            <div className="contact-form__header">
              <h2>{selectedCampaign.name}</h2>
              <button aria-label="Close broadcast details" className="icon-button" onClick={() => setSelectedCampaign(null)} type="button">X</button>
            </div>
            <dl className="deal-detail-list">
              <div><dt>Status</dt><dd>{selectedCampaign.status}</dd></div>
              <div><dt>Template</dt><dd>{selectedCampaign.template_name}</dd></div>
              <div><dt>Audience</dt><dd>{selectedCampaign.audience_summary}</dd></div>
              <div><dt>Recipients</dt><dd>{selectedCampaign.recipient_count}</dd></div>
              <div><dt>Sent</dt><dd>{selectedCampaign.sent_count}</dd></div>
              <div><dt>Delivered</dt><dd>{selectedCampaign.delivered_count}</dd></div>
              <div><dt>Read</dt><dd>{selectedCampaign.read_count}</dd></div>
              <div><dt>Failed</dt><dd>{selectedCampaign.failed_count}</dd></div>
            </dl>
            <div className="broadcast-template-preview">
              <strong>Template body</strong>
              <p>{selectedCampaign.template_body}</p>
            </div>
            <div className="table-wrap contacts-table-scroll">
              <table className="contacts-table broadcast-recipient-table">
                <thead>
                  <tr>
                    <th>Contact</th>
                    <th>Phone</th>
                    <th>Status</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedCampaign.recipients || []).map((recipient) => (
                    <tr key={recipient.id}>
                      <td>{recipient.contact_name || "-"}</td>
                      <td>{recipient.phone}</td>
                      <td>{recipient.status}</td>
                      <td>{recipient.error_message || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

export default Broadcasts;
