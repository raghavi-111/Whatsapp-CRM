import { useEffect, useMemo, useState } from "react";
import { Plus, Save, X } from "lucide-react";

import { getContacts } from "../services/contactService.js";
import { createDeal, getDeals, updateDeal } from "../services/pipelineService.js";
import "./Pipelines.css";

const defaultStages = ["New", "Qualified", "Proposal", "Won"];
const emptyDeal = {
  title: "",
  value: "",
  stage: "New",
  contact: "",
  notes: "",
  contactMode: "existing",
  customerName: "",
  phoneNumber: "",
  email: "",
  company: "",
  leadNotes: "",
  leadSource: "manual",
};
const emptyDealDetails = { title: "", value: "0", stage: "New", notes: "" };

function formatCurrency(value) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
    style: "currency",
    currency: "USD",
  });
}

function requestErrorMessage(error, fallback) {
  const data = error.response?.data;
  if (data?.detail) return data.detail;
  if (data?.contact?.[0]) return data.contact[0];
  if (data?.title?.[0]) return data.title[0];
  if (data?.value?.[0]) return data.value[0];
  if (data?.new_lead) {
    if (typeof data.new_lead === "string") return data.new_lead;
    const firstError = Object.values(data.new_lead).flat()[0];
    if (firstError) return firstError;
  }
  if (data?.non_field_errors?.[0]) return data.non_field_errors[0];
  return fallback;
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function Pipelines() {
  const [deals, setDeals] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [selectedDeal, setSelectedDeal] = useState(null);
  const [detailForm, setDetailForm] = useState(emptyDealDetails);
  const [formData, setFormData] = useState(emptyDeal);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [updatingDealId, setUpdatingDealId] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadBoard();
  }, []);

  async function loadBoard() {
    setIsLoading(true);
    setError("");
    try {
      const [dealData, contactData] = await Promise.all([getDeals(), getContacts()]);
      setDeals(dealData);
      setContacts(contactData);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to load pipeline deals."));
    } finally {
      setIsLoading(false);
    }
  }

  const totals = useMemo(
    () =>
      defaultStages.map((stage) => ({
        stage,
        deals: deals.filter((deal) => deal.stage === stage),
        stageValue: deals
          .filter((deal) => deal.stage === stage)
          .reduce((sum, deal) => sum + Number(deal.value || 0), 0),
      })),
    [deals],
  );

  const totalOpenValue = useMemo(
    () => deals.filter((deal) => deal.status === "open").reduce((sum, deal) => sum + Number(deal.value || 0), 0),
    [deals],
  );

  function updateField(event) {
    setFormData((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function updateDetailField(event) {
    setDetailForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function openCreateDealForm() {
    setFormData(emptyDeal);
    setMessage("");
    setError("");
    setShowForm(true);
  }

  async function handleCreateDeal(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    const payload = {
      title: formData.title,
      value: formData.value || "0",
      stage: formData.stage,
      source: "manual",
      notes: formData.notes,
    };
    if (formData.contactMode === "existing" && formData.contact) {
      payload.contact = Number(formData.contact);
    }
    if (formData.contactMode === "new") {
      payload.new_lead = {
        customer_name: formData.customerName,
        phone_number: formData.phoneNumber,
        email: formData.email,
        company: formData.company,
        notes: formData.leadNotes,
        source: formData.leadSource,
      };
    }

    try {
      await createDeal(payload);
      setFormData(emptyDeal);
      setShowForm(false);
      setMessage("Deal created.");
      await loadBoard();
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to create deal."));
    } finally {
      setIsSaving(false);
    }
  }

  function openDealDetails(deal) {
    setSelectedDeal(deal);
    setDetailForm({
      title: deal.title || "",
      value: deal.value ?? "0",
      stage: deal.stage || "New",
      notes: deal.notes || "",
    });
    setError("");
    setMessage("");
  }

  async function handleDealDetailSubmit(event) {
    event.preventDefault();
    if (!selectedDeal) return;

    const numericValue = Number(detailForm.value);
    if (detailForm.value === "" || Number.isNaN(numericValue)) {
      setError("Deal value must be numeric.");
      return;
    }
    if (numericValue < 0) {
      setError("Deal value cannot be negative.");
      return;
    }
    if (!detailForm.title.trim()) {
      setError("Deal title is required.");
      return;
    }

    setUpdatingDealId(selectedDeal.id);
    setError("");
    setMessage("");
    try {
      await updateDeal(selectedDeal.id, {
        title: detailForm.title,
        value: String(numericValue),
        stage: detailForm.stage,
        notes: detailForm.notes,
      });
      setMessage("Deal updated.");
      await loadBoard();
      closeDealDetails();
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to update deal."));
    } finally {
      setUpdatingDealId(null);
    }
  }

  function closeDealDetails() {
    setSelectedDeal(null);
    setDetailForm(emptyDealDetails);
    setError("");
  }

  return (
    <section className="dashboard-page pipelines-page">
      <div className="dashboard-header pipelines-page__header">
        <div>
          <h1>Pipelines</h1>
          <p>Track opportunities through every sales stage.</p>
        </div>
        <button className="button button--primary" onClick={openCreateDealForm} type="button">
          <Plus size={16} aria-hidden="true" />
          New deal
        </button>
      </div>

      {!showForm && !selectedDeal && message ? <p className="form-success">{message}</p> : null}
      {!showForm && !selectedDeal && error ? <p className="form-error">{error}</p> : null}

      {showForm ? (
        <form className="panel contact-form" onSubmit={handleCreateDeal}>
          <h2>Create deal</h2>
          <fieldset className="deal-contact-toggle">
            <legend>Customer</legend>
            <label>
              <input
                checked={formData.contactMode === "existing"}
                name="contactMode"
                onChange={updateField}
                type="radio"
                value="existing"
              />
              Existing Contact
            </label>
            <label>
              <input
                checked={formData.contactMode === "new"}
                name="contactMode"
                onChange={updateField}
                type="radio"
                value="new"
              />
              New Lead
            </label>
          </fieldset>
          <div className="form-grid">
            <label>
              Deal name
              <input name="title" onChange={updateField} required type="text" value={formData.title} />
            </label>
            <label>
              Value
              <input min="0" name="value" onChange={updateField} type="number" value={formData.value} />
            </label>
            <label>
              Stage
              <select name="stage" onChange={updateField} value={formData.stage}>
                {defaultStages.map((stage) => (
                  <option key={stage} value={stage}>
                    {stage}
                  </option>
                ))}
              </select>
            </label>
            {formData.contactMode === "existing" ? (
              <label>
                Contact
                <select name="contact" onChange={updateField} value={formData.contact}>
                  <option value="">No contact linked</option>
                  {contacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {contact.full_name || contact.phone_number}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <>
                <label>
                  Customer name
                  <input name="customerName" onChange={updateField} required type="text" value={formData.customerName} />
                </label>
                <label>
                  Mobile number
                  <input name="phoneNumber" onChange={updateField} required type="tel" value={formData.phoneNumber} />
                </label>
                <label>
                  Email
                  <input name="email" onChange={updateField} type="email" value={formData.email} />
                </label>
                <label>
                  Company
                  <input name="company" onChange={updateField} type="text" value={formData.company} />
                </label>
                <label>
                  Source
                  <select name="leadSource" onChange={updateField} value={formData.leadSource}>
                    <option value="manual">Manual</option>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="website">Website</option>
                    <option value="referral">Referral</option>
                    <option value="walk_in">Walk-in</option>
                  </select>
                </label>
                <label>
                  Lead notes
                  <textarea name="leadNotes" onChange={updateField} rows="3" value={formData.leadNotes} />
                </label>
              </>
            )}
          </div>
          <label>
            Notes
            <textarea name="notes" onChange={updateField} rows="3" value={formData.notes} />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <div className="actions">
            <button className="button button--primary" disabled={isSaving} type="submit">
              <Save size={16} aria-hidden="true" />
              {isSaving ? "Saving..." : "Save Deal"}
            </button>
            <button className="button" disabled={isSaving} onClick={() => setShowForm(false)} type="button">
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {isLoading ? <p className="dashboard-loading">Loading pipeline deals...</p> : null}

      {!isLoading && deals.length === 0 ? (
        <div className="empty-state">
          <strong>No deals yet</strong>
          <span>New WhatsApp contacts and manually created deals will appear here.</span>
        </div>
      ) : null}

      <div className="pipeline-board">
        {totals.map(({ stage, deals: stageDeals }) => (
          <article className="pipeline-stage" key={stage}>
            <header>
              <h2>{stage}</h2>
              <span>{stageDeals.length}</span>
            </header>
            {stageDeals.length === 0 ? (
              <div className="empty-state compact">
                <strong>No deals</strong>
                <span>New opportunities in this stage will appear here.</span>
              </div>
            ) : (
              stageDeals.map((deal) => (
                <button className="deal-card deal-card--compact" key={deal.id} onClick={() => openDealDetails(deal)} type="button">
                  <span className="deal-card__heading"><strong>{deal.contact_name || deal.title || "Untitled lead"}</strong><b>{formatCurrency(deal.value)}</b></span>
                  <span className="deal-card__badges">
                    {deal.source ? <small className="badge">{deal.source}</small> : null}
                    {deal.status && deal.status !== "open" ? (
                      <small className={`pill pill--${deal.status}`}>{deal.status}</small>
                    ) : null}
                  </span>
                </button>
              ))
            )}
          </article>
        ))}
      </div>

      {selectedDeal ? (
        <div className="deal-modal" role="presentation">
          <div className="contact-modal__scrim" onClick={closeDealDetails} />
          <form aria-modal="true" className="panel deal-detail-modal" onSubmit={handleDealDetailSubmit} role="dialog">
            <div className="contact-form__header">
              <h2>Deal details</h2>
              <button aria-label="Close deal details" className="icon-button" onClick={closeDealDetails} type="button">
                <X size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="form-grid">
              <label>
                Deal title
                <input
                  disabled={updatingDealId === selectedDeal.id}
                  name="title"
                  onChange={updateDetailField}
                  required
                  type="text"
                  value={detailForm.title}
                />
              </label>
              <label>
                Deal value
                <input
                  disabled={updatingDealId === selectedDeal.id}
                  min="0"
                  name="value"
                  onChange={updateDetailField}
                  required
                  step="0.01"
                  type="number"
                  value={detailForm.value}
                />
              </label>
              <label>
                Stage
                <select
                  disabled={updatingDealId === selectedDeal.id}
                  name="stage"
                  onChange={updateDetailField}
                  value={detailForm.stage}
                >
                  {defaultStages.map((nextStage) => (
                    <option key={nextStage} value={nextStage}>
                      {nextStage}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <dl className="deal-detail-list">
              <div>
                <dt>Contact</dt>
                <dd>{selectedDeal.contact_name || "No contact linked"}</dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{selectedDeal.contact_phone_number || "-"}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{selectedDeal.source || "-"}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{selectedDeal.status || "-"}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatDate(selectedDeal.created_at)}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{formatDate(selectedDeal.updated_at)}</dd>
              </div>
            </dl>

            <label>
              Notes
              <textarea
                disabled={updatingDealId === selectedDeal.id}
                name="notes"
                onChange={updateDetailField}
                rows="4"
                value={detailForm.notes}
              />
            </label>

            {error ? <p className="form-error">{error}</p> : null}

            {updatingDealId === selectedDeal.id ? <p className="dashboard-loading">Updating deal...</p> : null}

            <div className="actions">
              <button className="button button--primary" disabled={updatingDealId === selectedDeal.id} type="submit">
                <Save size={16} aria-hidden="true" />
                {updatingDealId === selectedDeal.id ? "Saving..." : "Save Changes"}
              </button>
              <button className="button" disabled={updatingDealId === selectedDeal.id} onClick={closeDealDetails} type="button">
                Cancel
              </button>
            </div>
          </form>
        </div>
      ) : null}

      <div className="dashboard-chart-grid pipeline-bottom-grid">
        <article className="panel chart-panel pipeline-analytics-panel">
          <h2>Pipeline analytics</h2>
          <p>Deal value by stage.</p>
          <div className="pipeline-analytics">
            {totals.map(({ stage, stageValue }) => (
              <div className="pipeline-analytics__row" key={stage}><div><span>{stage}</span><strong>{formatCurrency(stageValue)}</strong></div><div className={`pipeline-stage-track pipeline-stage-track--${stage.toLowerCase()}`}><i style={{ width: `${totalOpenValue ? Math.max(stageValue ? 4 : 0, stageValue / totalOpenValue * 100) : 0}%` }} /></div></div>
            ))}
            <div className="pipeline-analytics__row pipeline-analytics__row--total">
              <span>Total open</span>
              <strong>{formatCurrency(totalOpenValue)}</strong>
            </div>
          </div>
        </article>
        <article className="panel chart-panel pipeline-settings-panel">
          <h2>Stage settings</h2>
          <p>Configure stage names, order, and colors.</p>
          <div className="tag-list">
            {defaultStages.map((stage) => (
              <span className="tag-pill" key={stage}>{stage}</span>
            ))}
          </div>
          <button className="button" type="button">Manage stages</button>
        </article>
      </div>
    </section>
  );
}

export default Pipelines;
