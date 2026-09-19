import { useEffect, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { ChevronLeft, ChevronRight, MessageSquare, MoreHorizontal, Pencil, Plus, Save, Search, Tags, Trash2, Upload, UserRound, X } from "lucide-react";
import WhatsAppExcelImport from "../components/contacts/WhatsAppExcelImport.jsx";

import {
  createContact,
  deleteContact,
  getContactCategories,
  getContacts,
  startContactConversation,
  updateContact,
} from "../services/contactService.js";
import {
  createContactNote,
  getContactNotes,
  getTags,
  updateContactTags,
} from "../services/supportService.js";
import { clearTokens } from "../../shared/services/tokenStorage.js";
import { notify } from "../../shared/services/notificationService.js";

/**
 * Contacts Page
 *
 * Route-level CRM contact workspace. Manages contact CRUD, search/filtering,
 * tags, notes, and the handoff into Inbox conversations.
 */

const emptyContact = {
  full_name: "",
  phone_number: "",
  email: "",
  company_name: "",
  source: "manual",
  status: "new",
  notes: "",
};

function Contacts() {
  const navigate = useNavigate();
  const { role = "agent" } = useOutletContext() || {};

  // Contact list state and modal form state are kept together so create/edit refreshes stay local.
  const [contacts, setContacts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);
  const [selectedTagIds, setSelectedTagIds] = useState([]);
  const [contactNotes, setContactNotes] = useState([]);
  const [contactNoteText, setContactNoteText] = useState("");
  const [formData, setFormData] = useState(emptyContact);
  const [editingContactId, setEditingContactId] = useState(null);
  const [isContactFormOpen, setIsContactFormOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [openActionMenuId, setOpenActionMenuId] = useState(null);
  const [filters, setFilters] = useState({ search: "", status: "", source: "", category: "", tag: "" });
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadContacts();
    loadTags();
    getContactCategories().then(setCategories).catch(() => setError("Unable to load contact categories."));
  }, []);

  async function loadContacts(nextFilters = filters) {
    setIsLoading(true);
    setError("");

    try {
      const { tag: _tag, ...apiFilters } = nextFilters;
      const data = await getContacts(apiFilters);
      setContacts(data);
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        clearTokens();
        navigate("/login", { replace: true });
        return;
      }
      setError("Unable to load contacts.");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadTags() {
    try {
      setTags(await getTags());
    } catch {
      setError("Unable to load tags.");
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
    setCurrentPage(1);
    loadContacts(nextFilters);
  }

  function openCreateContactForm() {
    resetForm();
    setMessage("");
    setError("");
    setIsContactFormOpen(true);
  }

  function closeContactForm() {
    resetForm();
    setIsContactFormOpen(false);
  }

  function startEdit(contact) {
    setOpenActionMenuId(null);
    setEditingContactId(contact.id);
    setFormData({
      full_name: contact.full_name || "",
      phone_number: contact.phone_number || "",
      email: contact.email || "",
      company_name: contact.company_name || "",
      source: contact.source || "manual",
      status: contact.status || "new",
      notes: contact.notes || "",
    });
    setMessage("");
    setError("");
    setIsContactFormOpen(true);
  }

  async function manageContact(contact) {
    setOpenActionMenuId(null);
    setSelectedContact(contact);
    setSelectedTagIds((contact.tags || []).map((tag) => tag.id));
    setContactNoteText("");
    try {
      setContactNotes(await getContactNotes(contact.id));
    } catch {
      setError("Unable to load contact notes.");
    }
  }

  async function saveContactTags(event) {
    event.preventDefault();
    if (!selectedContact) return;
    try {
      const updatedContact = await updateContactTags(selectedContact.id, selectedTagIds.map(Number));
      setSelectedContact(updatedContact);
      setContacts((current) =>
        current.map((contact) => (contact.id === updatedContact.id ? updatedContact : contact)),
      );
      setMessage("Contact tags updated.");
    } catch {
      setError("Unable to update contact tags.");
    }
  }

  async function addContactNote(event) {
    event.preventDefault();
    if (!selectedContact || !contactNoteText.trim()) return;
    try {
      await createContactNote(selectedContact.id, contactNoteText);
      setContactNoteText("");
      setContactNotes(await getContactNotes(selectedContact.id));
      setMessage("Contact note added.");
    } catch {
      setError("Unable to add contact note.");
    }
  }

  function resetForm() {
    setEditingContactId(null);
    setFormData(emptyContact);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      if (editingContactId) {
        await updateContact(editingContactId, formData);
        setMessage("Contact updated.");
      } else {
        await createContact(formData);
        setMessage("Contact created.");
      }

      resetForm();
      setIsContactFormOpen(false);
      await loadContacts();
    } catch (requestError) {
      const data = requestError.response?.data;
      setError(data?.phone_number?.[0] || data?.non_field_errors?.[0] || "Unable to save contact.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(contact) {
    setOpenActionMenuId(null);
    const confirmed = window.confirm(`Delete ${contact.full_name || contact.phone_number}?`);
    if (!confirmed) return;

    setError("");
    setMessage("");

    try {
      await deleteContact(contact.id);
      setMessage("Contact deleted.");
      await loadContacts();
    } catch {
      setError("Unable to delete contact.");
    }
  }

  async function openChat(contact) {
    setOpenActionMenuId(null);
    setError("");
    setMessage("");

    try {
      const data = await startContactConversation(contact.id);
      notify(
        "success",
        data.created ? "Conversation started" : "Conversation opened",
        contact.full_name || contact.phone_number,
      );
      navigate(`/inbox?conversation=${data.conversation_id}`);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail || "Unable to open chat.";
      setError(detail);
      notify("error", "Unable to open chat", detail);
    }
  }

  const filteredContacts = filters.tag
    ? contacts.filter((contact) => (contact.tags || []).some((tag) => String(tag.id) === filters.tag))
    : contacts;
  const pageSize = 10;
  const pageCount = Math.max(1, Math.ceil(filteredContacts.length / pageSize));
  const safePage = Math.min(currentPage, pageCount);
  const pageStart = (safePage - 1) * pageSize;
  const visibleContacts = filteredContacts.slice(pageStart, pageStart + pageSize);

  return (
    <section className="dashboard-page contacts-page">
      <div className="dashboard-header contacts-page__header">
        <div>
          <h1>Contacts</h1>
          <p>Manage customer records, tags, and conversation access.</p>
        </div>
        <div className="contacts-page__header-actions">
          <button className="button" onClick={() => setIsImportOpen(true)} type="button"><Upload size={16}/>Import WhatsApp Contacts</button>
          <button className="button button--primary contacts-create-button" onClick={openCreateContactForm} type="button">
            <Plus size={16} aria-hidden="true" />
            Create Contact
          </button>
        </div>
      </div>
      {isImportOpen ? <WhatsAppExcelImport categories={categories} onClose={() => setIsImportOpen(false)} onImported={loadContacts}/> : null}

      {!isContactFormOpen && message ? <p className="form-success">{message}</p> : null}
      {!isContactFormOpen && error ? <p className="form-error">{error}</p> : null}

      {isContactFormOpen ? (
        <div className="contact-modal" role="presentation">
          <div className="contact-modal__scrim" onClick={closeContactForm} />
          <form aria-modal="true" className="panel contact-form contact-form--modal" onSubmit={handleSubmit} role="dialog">
            <div className="contact-form__header">
              <h2>{editingContactId ? "Edit contact" : "Create contact"}</h2>
              <button aria-label="Close contact form" className="icon-button" onClick={closeContactForm} type="button">
                <X size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="form-grid">
              <label>
                Name
                <input name="full_name" onChange={updateFormField} type="text" value={formData.full_name} />
              </label>
              <label>
                Phone
                <input name="phone_number" onChange={updateFormField} required type="text" value={formData.phone_number} />
              </label>
              <label>
                Email
                <input name="email" onChange={updateFormField} type="email" value={formData.email} />
              </label>
              <label>
                Company
                <input name="company_name" onChange={updateFormField} type="text" value={formData.company_name} />
              </label>
              <label>
                Source
                <select name="source" onChange={updateFormField} value={formData.source}>
                  <option value="manual">Manual</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="import">Import</option>
                  <option value="website">Website</option>
                </select>
              </label>
              <label>
                Status
                <select name="status" onChange={updateFormField} value={formData.status}>
                  <option value="new">New</option>
                  <option value="active">Active</option>
                  <option value="blocked">Blocked</option>
                </select>
              </label>
            </div>

            <label>
              Notes
              <textarea name="notes" onChange={updateFormField} rows="3" value={formData.notes} />
            </label>

            {message ? <p className="form-success">{message}</p> : null}
            {error ? <p className="form-error">{error}</p> : null}

            <div className="actions">
              <button className="button button--primary" disabled={isSaving} type="submit">
                <Save size={16} aria-hidden="true" />
                {isSaving ? "Saving..." : editingContactId ? "Update Contact" : "Create Contact"}
              </button>
              <button className="button" onClick={closeContactForm} type="button">
                Cancel
              </button>
            </div>
          </form>
        </div>
      ) : null}

      <div className="contacts-filter-card">
        <label className="contacts-search-field">
          <Search size={15} aria-hidden="true" />
          <input aria-label="Search contacts" name="search" onChange={updateFilter} placeholder="Search name, phone, email, or company" type="search" value={filters.search}/>
        </label>
        <select aria-label="Filter by status" name="status" onChange={updateFilter} value={filters.status}>
          <option value="">All statuses</option><option value="new">New</option><option value="active">Active</option><option value="blocked">Blocked</option>
        </select>
        <select aria-label="Filter by source" name="source" onChange={updateFilter} value={filters.source}>
          <option value="">All sources</option><option value="manual">Manual</option><option value="whatsapp">WhatsApp</option><option value="import">Import</option><option value="website">Website</option><option value="lead_collector">Lead Collector</option>
        </select>
        <select aria-label="Filter by category" name="category" onChange={updateFilter} value={filters.category}>
          <option value="">All categories</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
        <select aria-label="Filter by tag" name="tag" onChange={updateFilter} value={filters.tag}>
          <option value="">All tags</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
        </select>
      </div>

      <div className="contacts-panel">
        {selectedContact ? (
          <div className="support-panel">
            <h2>Tags and notes for {selectedContact.full_name || selectedContact.phone_number}</h2>
            <form className="note-form" onSubmit={saveContactTags}>
              <label>
                Tags
                <select
                  multiple
                  onChange={(event) =>
                    setSelectedTagIds(Array.from(event.target.selectedOptions, (option) => option.value))
                  }
                  value={selectedTagIds.map(String)}
                >
                  {tags.map((tag) => (
                    <option key={tag.id} value={tag.id}>
                      {tag.name}
                    </option>
                  ))}
                </select>
              </label>
              <button className="button button--small" type="submit">Save Tags</button>
            </form>
            <form className="note-form" onSubmit={addContactNote}>
              <label>
                New note
                <textarea onChange={(event) => setContactNoteText(event.target.value)} rows="2" value={contactNoteText} />
              </label>
              <button className="button button--small" type="submit">Add Note</button>
            </form>
            <div className="notes-list">
              {contactNotes.map((note) => (
                <p key={note.id}>{note.note}</p>
              ))}
            </div>
          </div>
        ) : null}

        {isLoading ? <p>Loading contacts...</p> : null}
        {!isLoading && filteredContacts.length === 0 ? <p className="contacts-empty-state">No contacts found.</p> : null}

        {!isLoading && filteredContacts.length > 0 ? (
          <div className="table-wrap contacts-table-scroll">
            <table className="contacts-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>Company</th>
                  <th>Category</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Tags</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleContacts.map((contact) => (
                  <tr key={contact.id}>
                    <td>
                      <div className="contact-name-cell"><span className="contact-avatar"><UserRound aria-hidden="true" size={19} /></span><span className="contact-table__text">{contact.full_name || contact.phone_number || "Unknown contact"}</span></div>
                    </td>
                    <td>
                      <span className="contact-table__text contact-table__text--nowrap">{contact.phone_number}</span>
                    </td>
                    <td>
                      <span className="contact-table__text">{contact.email || "-"}</span>
                    </td>
                    <td>
                      <span className="contact-table__text">{contact.company_name || "-"}</span>
                    </td>
                    <td><span className="contact-table__text">{contact.category?.name || "-"}</span></td>
                    <td>
                      <span className="contact-source">{contact.source}</span>
                    </td>
                    <td>
                      <span className={`contact-status contact-status--${contact.status}`}>{contact.status}</span>
                    </td>
                    <td>
                      <div className="tag-list contact-table__tags">
                        {(contact.tags || []).map((tag) => (
                          <span className="tag-pill" key={tag.id} style={{ borderColor: tag.color }}>
                            {tag.name}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <div className="row-actions contact-table__actions">
                        <button className="button button--small" onClick={() => openChat(contact)} type="button">
                          <MessageSquare size={14} aria-hidden="true" />
                          Open
                        </button>
                        <div className="contact-action-menu">
                          <button
                            aria-expanded={openActionMenuId === contact.id}
                            aria-label={`More actions for ${contact.full_name || contact.phone_number}`}
                            className="icon-button contact-action-menu__trigger"
                            onClick={() => setOpenActionMenuId((current) => (current === contact.id ? null : contact.id))}
                            type="button"
                          >
                            <MoreHorizontal size={16} aria-hidden="true" />
                          </button>
                          {openActionMenuId === contact.id ? (
                            <div className="contact-action-menu__content">
                              <button onClick={() => manageContact(contact)} type="button">
                                <Tags size={14} aria-hidden="true" />
                                Tags/Notes
                              </button>
                              <button onClick={() => startEdit(contact)} type="button">
                                <Pencil size={14} aria-hidden="true" />
                                Edit
                              </button>
                              {role === "owner" || role === "admin" ? (
                                <button onClick={() => handleDelete(contact)} type="button">
                                  <Trash2 size={14} aria-hidden="true" />
                                  Delete
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {!isLoading && filteredContacts.length > 0 ? <footer className="contacts-pagination"><span>Showing {pageStart + 1}–{Math.min(pageStart + pageSize, filteredContacts.length)} of {filteredContacts.length} contacts</span><div><button disabled={safePage === 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} type="button"><ChevronLeft size={14}/>Previous</button><button disabled={safePage === pageCount} onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))} type="button">Next<ChevronRight size={14}/></button></div></footer> : null}
      </div>
    </section>
  );
}

export default Contacts;
