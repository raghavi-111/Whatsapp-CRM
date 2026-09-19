import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Pencil, Send, Trash2 } from "lucide-react";

/**
 * Templates Settings Panel
 *
 * WhatsApp template management surface used by Settings > Templates.
 * The full template body remains available in edit mode,
 * while table rows render a controlled preview.
 */
import {
  createTemplate,
  deleteTemplate,
  getTemplates,
  sendTemplate,
  updateTemplate,
} from "../../services/templateService.js";
import { getContacts } from "../../services/contactService.js";
import { clearTokens } from "../../../shared/services/tokenStorage.js";
import { SettingsCard, SettingsGrid, SettingsSection, SettingsTableWrapper } from "../../../shared/components/settings/SettingsLayout.jsx";

const emptyTemplate = {
  name: "",
  language: "en_US",
  category: "utility",
  status: "draft",
  header_type: "none",
  header_text: "",
  body_text: "",
  footer_text: "",
  buttons_json: [],
  meta_template_id: "",
};

function previewBody(text) {
  if (!text) return "-";
  const normalized = String(text).replace(/\s+/g, " ").trim();
  if (!normalized) return "-";
  return normalized.length > 52 ? `${normalized.slice(0, 52)}...` : normalized;
}

function displayValue(value) {
  return value || "-";
}

function Templates({ embedded = false }) {
  const navigate = useNavigate();

  // Template manager state covers list filters, edit form data, and send flow.
  const [templates, setTemplates] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [formData, setFormData] = useState(emptyTemplate);
  const [sendData, setSendData] = useState({ templateId: "", contactId: "", parameters: "" });
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [filters, setFilters] = useState({ search: "", category: "", status: "", language: "" });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingTemplateId, setDeletingTemplateId] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadTemplates();
    loadContacts();
  }, []);

  async function loadTemplates(nextFilters = filters) {
    setIsLoading(true);
    setError("");

    try {
      const data = await getTemplates(nextFilters);
      setTemplates(data);
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        clearTokens();
        navigate("/login", { replace: true });
        return;
      }
      setError("Unable to load templates.");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadContacts() {
    try {
      const data = await getContacts();
      setContacts(data);
    } catch {
      setError("Unable to load contacts for template sending.");
    }
  }

  function updateFormField(event) {
    setFormData((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function updateFilter(event) {
    const nextFilters = {
      ...filters,
      [event.target.name]: event.target.value,
    };
    setFilters(nextFilters);
    loadTemplates(nextFilters);
  }

  function startEdit(template) {
    setEditingTemplateId(template.id);
    setFormData({
      name: template.name || "",
      language: template.language || "en_US",
      category: template.category || "utility",
      status: template.status || "draft",
      header_type: template.header_type || "none",
      header_text: template.header_text || "",
      body_text: template.body_text || "",
      footer_text: template.footer_text || "",
      buttons_json: template.buttons_json || [],
      meta_template_id: template.meta_template_id || "",
    });
    setError("");
    setMessage("");
  }

  function resetForm() {
    setEditingTemplateId(null);
    setFormData(emptyTemplate);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      if (editingTemplateId) {
        await updateTemplate(editingTemplateId, formData);
        setMessage("Template updated.");
      } else {
        await createTemplate(formData);
        setMessage("Template created.");
      }

      resetForm();
      await loadTemplates();
    } catch (requestError) {
      const data = requestError.response?.data;
      setError(
        data?.name?.[0] ||
          data?.language?.[0] ||
          data?.body_text?.[0] ||
          data?.non_field_errors?.[0] ||
          "Unable to save template.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(template) {
    if (deletingTemplateId !== null) return;
    const confirmed = window.confirm(`Delete template ${template.name}?`);
    if (!confirmed) return;

    setDeletingTemplateId(template.id);
    setError("");
    setMessage("");

    try {
      await deleteTemplate(template.id);
      setTemplates((current) => current.filter((item) => item.id !== template.id));
      setSendData((current) =>
        String(current.templateId) === String(template.id)
          ? { ...current, templateId: "" }
          : current,
      );
      if (editingTemplateId === template.id) resetForm();
      setMessage("Template deleted.");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to delete template.");
    } finally {
      setDeletingTemplateId(null);
    }
  }

  function startSend(template) {
    setSendData((current) => ({
      ...current,
      templateId: template.id,
    }));
    setError("");
    setMessage("");
  }

  function updateSendField(event) {
    setSendData((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function handleSendTemplate(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      const parameters = sendData.parameters
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

      await sendTemplate(sendData.templateId, {
        contact_id: Number(sendData.contactId),
        parameters,
      });
      setMessage("Template message sent.");
      setSendData({ templateId: "", contactId: "", parameters: "" });
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.response?.data?.parameters?.[0] ||
          requestError.response?.data?.non_field_errors?.[0] ||
          "Unable to send template.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className={embedded ? "settings-embedded-page" : "dashboard-page"}>
      {!embedded ? (
      <div className="dashboard-header">
        <div>
          <h1>Templates</h1>
        </div>
        <Link className="button" to="/dashboard">
          Dashboard
        </Link>
      </div>
      ) : null}

      <SettingsSection>
      <SettingsGrid className="settings-grid--sidebar settings-template-editor">
      <SettingsCard as="form" className="contact-form settings-template-form settings-card--primary" onSubmit={handleSubmit}>
        <div className="settings-card__header"><div><h2>{editingTemplateId ? "Edit template" : "Create template"}</h2><p>Define the template basics, message content, and Meta identifiers.</p></div></div>

        <div className="settings-form-group"><h3>Template basics</h3>
        <div className="form-grid">
          <label>
            Name
            <input name="name" onChange={updateFormField} required type="text" value={formData.name} />
          </label>
          <label>
            Language
            <input name="language" onChange={updateFormField} required type="text" value={formData.language} />
          </label>
          <label>
            Category
            <select name="category" onChange={updateFormField} value={formData.category}>
              <option value="marketing">Marketing</option>
              <option value="utility">Utility</option>
              <option value="authentication">Authentication</option>
            </select>
          </label>
          <label>
            Status
            <select name="status" onChange={updateFormField} value={formData.status}>
              <option value="draft">Draft</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="paused">Paused</option>
            </select>
          </label>
          <label>
            Header Type
            <select name="header_type" onChange={updateFormField} value={formData.header_type}>
              <option value="none">None</option>
              <option value="text">Text</option>
              <option value="image">Image</option>
              <option value="document">Document</option>
              <option value="video">Video</option>
            </select>
          </label>
          <label>
            Header Text
            <input name="header_text" onChange={updateFormField} type="text" value={formData.header_text} />
          </label>
        </div>
        </div>

        <div className="settings-form-group"><h3>Message content</h3>
        <label>
          Body Text
          <textarea name="body_text" onChange={updateFormField} required rows="4" value={formData.body_text} />
        </label>

        <div className="form-grid">
          <label>
            Footer Text
            <input name="footer_text" onChange={updateFormField} type="text" value={formData.footer_text} />
          </label>
          <label>
            Meta Template ID
            <input name="meta_template_id" onChange={updateFormField} type="text" value={formData.meta_template_id} />
          </label>
        </div>
        </div>

        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <div className="actions settings-actions">
          <button className="button button--primary" disabled={isSaving} type="submit">
            {isSaving ? "Saving..." : editingTemplateId ? "Update Template" : "Create Template"}
          </button>
          {editingTemplateId ? (
            <button className="button" onClick={resetForm} type="button">
              Cancel
            </button>
          ) : null}
        </div>
      </SettingsCard>

      <SettingsCard className="settings-template-preview">
        <div className="settings-card__header"><div><h2>Message preview</h2><p>Preview of the content customers will receive.</p></div></div>
        <div className="template-preview-message">
          {formData.header_type !== "none" && formData.header_text ? <strong>{formData.header_text}</strong> : null}
          <p>{formData.body_text || "Your template body will appear here."}</p>
          {formData.footer_text ? <small>{formData.footer_text}</small> : null}
        </div>
        <div className="settings-help-list"><span>Language: {formData.language}</span><span>Category: {formData.category}</span><span>Status: {formData.status}</span></div>
      </SettingsCard>
      </SettingsGrid>

      <SettingsCard className="contacts-panel settings-table-card">
        <form className="send-template-form" onSubmit={handleSendTemplate}>
          <div className="send-template-form__header">
            <h2>Send approved template</h2>
            <p>Select an approved template, choose a contact, and provide optional comma-separated parameters.</p>
          </div>
          <div className="send-template-form__grid">
            <label>
              Template
              <select name="templateId" onChange={updateSendField} required value={sendData.templateId}>
                <option value="">Choose template</option>
                {templates
                  .filter((template) => template.status === "approved")
                  .map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} ({template.language})
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Contact
              <select name="contactId" onChange={updateSendField} required value={sendData.contactId}>
                <option value="">Choose contact</option>
                {contacts.map((contact) => (
                  <option key={contact.id} value={contact.id}>
                    {contact.full_name || contact.phone_number}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Parameters
              <input
                name="parameters"
                onChange={updateSendField}
                placeholder="Parameters, comma separated"
                type="text"
                value={sendData.parameters}
              />
            </label>
            <button className="button button--primary send-template-form__button" disabled={isSaving} type="submit">
              <Send size={16} aria-hidden="true" />
              Send Template
            </button>
          </div>
        </form>

        <div className="filters">
          <input
            aria-label="Search templates"
            name="search"
            onChange={updateFilter}
            placeholder="Search templates"
            type="search"
            value={filters.search}
          />
          <select aria-label="Filter by category" name="category" onChange={updateFilter} value={filters.category}>
            <option value="">All categories</option>
            <option value="marketing">Marketing</option>
            <option value="utility">Utility</option>
            <option value="authentication">Authentication</option>
          </select>
          <select aria-label="Filter by status" name="status" onChange={updateFilter} value={filters.status}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="paused">Paused</option>
          </select>
          <input
            aria-label="Filter by language"
            name="language"
            onChange={updateFilter}
            placeholder="Language"
            type="text"
            value={filters.language}
          />
        </div>

        {isLoading ? <p>Loading templates...</p> : null}
        {!isLoading && templates.length === 0 ? <p>No templates found.</p> : null}

        {!isLoading && templates.length > 0 ? (
          <SettingsTableWrapper className="templates-table-scroll">
            <table className="contacts-table templates-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Language</th>
                  <th>Header Type</th>
                  <th>Body Preview</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => (
                  <tr key={template.id}>
                    <td><span className="template-cell-text">{displayValue(template.name)}</span></td>
                    <td><span className="template-cell-meta">{displayValue(template.category)}</span></td>
                    <td><span className="template-cell-meta">{displayValue(template.status)}</span></td>
                    <td><span className="template-cell-meta">{displayValue(template.language)}</span></td>
                    <td><span className="template-cell-meta">{displayValue(template.header_type)}</span></td>
                    <td>
                      <span className="template-body-preview">
                        {previewBody(template.body_text)}
                      </span>
                    </td>
                    <td>
                      <div className="row-actions templates-table__actions">
                        <button className="button button--small" onClick={() => startEdit(template)} type="button">
                          <Pencil size={14} aria-hidden="true" />
                          Edit
                        </button>
                        {template.status === "approved" ? (
                          <button className="button button--small" onClick={() => startSend(template)} type="button">
                            <Send size={14} aria-hidden="true" />
                            Send
                          </button>
                        ) : null}
                        <button
                          className="button button--small"
                          disabled={deletingTemplateId !== null}
                          onClick={() => handleDelete(template)}
                          type="button"
                        >
                          <Trash2 size={14} aria-hidden="true" />
                          {deletingTemplateId === template.id ? "Deleting..." : "Delete"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SettingsTableWrapper>
        ) : null}
      </SettingsCard>
      </SettingsSection>
    </section>
  );
}

export default Templates;
