import { useEffect, useRef, useState } from "react";
import { useNavigate, useOutletContext, useSearchParams } from "react-router-dom";
import { ArrowLeft, FileText, Image, Info, MoreHorizontal, Plus, Search, Send, UserRound } from "lucide-react";

import {
  createMessage,
  getConversations,
  getMessages,
  uploadMediaMessage,
} from "../services/conversationService.js";
import { getOrganizationMembers } from "../../shared/services/organizationService.js";
import {
  assignConversation,
  createContactNote,
  createConversationNote,
  getContactNotes,
  getConversationNotes,
  getTags,
  updateContactTags,
  updateConversationStatus,
} from "../services/supportService.js";
import { getTemplates, sendTemplate } from "../services/templateService.js";
import { clearTokens } from "../../shared/services/tokenStorage.js";
import { connectInboxWebSocket } from "../services/websocketClient.js";
import { notify } from "../../shared/services/notificationService.js";
import MessageMedia from "../components/inbox/MessageMedia.jsx";

/**
 * Inbox Page
 *
 * Route-level WhatsApp conversation workspace. Handles conversation loading,
 * message history, assignment/tag/note support, outbound messages, template
 * sends, media upload, and realtime updates through the inbox WebSocket.
 */

function formatTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function relativeTime(value) {
  if (!value) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function detectMediaType(file) {
  if (!file) return "image";
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type.startsWith("video/")) return "video";
  return "document";
}

function Inbox() {
  const navigate = useNavigate();
  const { role = "agent" } = useOutletContext() || {};
  const [searchParams, setSearchParams] = useSearchParams();

  // Conversation and message state drive the selected Inbox thread.
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);

  // Composer state covers text, media uploads, and approved template sends.
  const [filters, setFilters] = useState({ search: "", status: "" });
  const [composerText, setComposerText] = useState("");
  const [mediaFile, setMediaFile] = useState(null);
  const [mediaMessageType, setMediaMessageType] = useState("image");
  const [mediaCaption, setMediaCaption] = useState("");
  const [mediaProgress, setMediaProgress] = useState(0);
  const [approvedTemplates, setApprovedTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [templateParameters, setTemplateParameters] = useState("");
  const [activeComposerPanel, setActiveComposerPanel] = useState("");
  const [tags, setTags] = useState([]);
  const [members, setMembers] = useState([]);
  const [contactNotes, setContactNotes] = useState([]);
  const [conversationNotes, setConversationNotes] = useState([]);
  const [selectedTagIds, setSelectedTagIds] = useState([]);
  const [contactNoteText, setContactNoteText] = useState("");
  const [conversationNoteText, setConversationNoteText] = useState("");
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [liveStatus, setLiveStatus] = useState("disconnected");
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const detailsRef = useRef(null);
  const detailsTriggerRef = useRef(null);
  const selectedConversationRef = useRef(null);
  const filtersRef = useRef(filters);
  const isLiveConnected = liveStatus === "connected";
  const liveStatusLabel = isLiveConnected ? "Live connection active" : "Live connection disconnected";

  useEffect(() => {
    const requestedConversationId = Number(searchParams.get("conversation") || "");
    loadConversations(filters, requestedConversationId || undefined);
    loadApprovedTemplates();
  }, []);

  useEffect(() => {
    loadSidebarOptions();
  }, [role]);

  useEffect(() => {
    selectedConversationRef.current = selectedConversation;
  }, [selectedConversation]);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    return connectInboxWebSocket({
      onStatus: setLiveStatus,
      onEvent: handleRealtimeEvent,
    });
  }, []);

  useEffect(() => {
    const close = (event) => {
      if (event.key === "Escape" && isDetailsOpen) {
        setIsDetailsOpen(false);
        requestAnimationFrame(() => detailsTriggerRef.current?.focus());
      }
    };
    document.addEventListener("keydown", close);
    if (isDetailsOpen && window.innerWidth <= 1279) requestAnimationFrame(() => detailsRef.current?.focus());
    return () => document.removeEventListener("keydown", close);
  }, [isDetailsOpen]);

  async function handleRealtimeEvent(event) {
    if (!event?.event_type || event.event_type === "connected") return;

    if (event.event_type === "message.created") {
      notify("info", "Message received", "The inbox has new message activity.");
    } else if (event.event_type === "message.status_updated") {
      notify("info", "Delivery status updated", `Status: ${event.delivery_status || "updated"}`);
    } else if (event.event_type.includes("automation")) {
      notify("warning", "Automation event", event.event_type);
    }

    const currentConversation = selectedConversationRef.current;
    await loadConversations(filtersRef.current, currentConversation?.id);

    if (currentConversation && event.conversation_id === currentConversation.id) {
      await loadMessages(currentConversation.id);
      await loadSidebarData(currentConversation);
    }
  }

  async function loadSidebarOptions() {
    try {
      const tagData = await getTags();
      setTags(tagData);

      if (role === "owner" || role === "admin") {
        const memberData = await getOrganizationMembers();
        setMembers(memberData.filter((member) => member.status === "active"));
      } else {
        setMembers([]);
      }
    } catch (requestError) {
      if (requestError.response?.status !== 403) {
        setError("Unable to load inbox sidebar options.");
      }
    }
  }

  async function loadApprovedTemplates() {
    try {
      const data = await getTemplates({ status: "approved" });
      setApprovedTemplates(data);
    } catch {
      setError("Unable to load approved templates.");
    }
  }

  async function loadConversations(nextFilters = filters, preferredConversationId = selectedConversation?.id) {
    setIsLoadingConversations(true);
    setError("");

    try {
      const data = await getConversations({
        ...nextFilters,
        ordering: "-last_message_at",
      });
      setConversations(data);

      const preferredId = Number(preferredConversationId || 0);
      const shouldAutoSelect = window.innerWidth > 900 || preferredId > 0;
      const nextSelected =
        data.find((conversation) => Number(conversation.id) === preferredId) ||
        (shouldAutoSelect ? data[0] : null) ||
        null;
      setSelectedConversation(nextSelected);

      if (nextSelected) {
        await loadMessages(nextSelected.id);
        await loadSidebarData(nextSelected);
      } else {
        setMessages([]);
        setContactNotes([]);
        setConversationNotes([]);
      }
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        clearTokens();
        navigate("/login", { replace: true });
        return;
      }
      setError("Unable to load conversations.");
    } finally {
      setIsLoadingConversations(false);
    }
  }

  async function loadMessages(conversationId) {
    setIsLoadingMessages(true);
    setError("");

    try {
      const data = await getMessages(conversationId);
      setMessages(data);
    } catch {
      setError("Unable to load messages.");
    } finally {
      setIsLoadingMessages(false);
    }
  }

  function updateFilter(event) {
    const nextFilters = {
      ...filters,
      [event.target.name]: event.target.value,
    };
    setFilters(nextFilters);
    loadConversations(nextFilters);
  }

  async function selectConversation(conversation) {
    setSearchParams({});
    setSelectedConversation(conversation);
    await loadMessages(conversation.id);
    await loadSidebarData(conversation);
  }

  function returnToConversationList() {
    setSearchParams({});
    setSelectedConversation(null);
    setMessages([]);
    setContactNotes([]);
    setConversationNotes([]);
    setIsDetailsOpen(false);
  }

  async function loadSidebarData(conversation) {
    setSelectedTagIds((conversation.contact_tags || []).map((tag) => tag.id));
    try {
      const [nextContactNotes, nextConversationNotes] = await Promise.all([
        getContactNotes(conversation.contact),
        getConversationNotes(conversation.id),
      ]);
      setContactNotes(nextContactNotes);
      setConversationNotes(nextConversationNotes);
    } catch {
      setError("Unable to load notes.");
    }
  }

  async function updateStatus(event) {
    if (!selectedConversation) return;

    try {
      const updatedConversation = await updateConversationStatus(selectedConversation.id, event.target.value);
      setSelectedConversation(updatedConversation);
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === updatedConversation.id ? updatedConversation : conversation,
        ),
      );
    } catch {
      setError("Unable to update conversation status.");
    }
  }

  async function updateAssignedAgent(event) {
    if (!selectedConversation) return;
    try {
      const updatedConversation = await assignConversation(selectedConversation.id, event.target.value || null);
      setSelectedConversation(updatedConversation);
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === updatedConversation.id ? updatedConversation : conversation,
        ),
      );
    } catch {
      setError("Unable to assign conversation.");
    }
  }

  async function saveContactTags(event) {
    event.preventDefault();
    if (!selectedConversation) return;
    try {
      const updatedContact = await updateContactTags(selectedConversation.contact, selectedTagIds.map(Number));
      const updatedConversation = { ...selectedConversation, contact_tags: updatedContact.tags };
      setSelectedConversation(updatedConversation);
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === updatedConversation.id ? updatedConversation : conversation,
        ),
      );
    } catch {
      setError("Unable to update contact tags.");
    }
  }

  async function addContactNote(event) {
    event.preventDefault();
    if (!selectedConversation || !contactNoteText.trim()) return;
    try {
      await createContactNote(selectedConversation.contact, contactNoteText);
      setContactNoteText("");
      setContactNotes(await getContactNotes(selectedConversation.contact));
    } catch {
      setError("Unable to add contact note.");
    }
  }

  async function addConversationNote(event) {
    event.preventDefault();
    if (!selectedConversation || !conversationNoteText.trim()) return;
    try {
      await createConversationNote(selectedConversation.id, conversationNoteText);
      setConversationNoteText("");
      setConversationNotes(await getConversationNotes(selectedConversation.id));
    } catch {
      setError("Unable to add conversation note.");
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!selectedConversation || !composerText.trim()) return;

    setIsSending(true);
    setError("");

    try {
      await createMessage(selectedConversation.id, {
        text: composerText,
        sender_type: "agent",
        direction: "outbound",
        message_type: "text",
        delivery_status: "pending",
      });
      notify("success", "Message sent", "Your WhatsApp text message was queued.");
      setComposerText("");
      await loadConversations(filters, selectedConversation.id);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      const failedMessage = requestError.response?.data?.message;

      if (failedMessage) {
        setMessages((current) => [...current, failedMessage]);
      }

      setError(detail || "Unable to send WhatsApp message.");
    } finally {
      setIsSending(false);
    }
  }

  async function sendSelectedTemplate() {
    if (!selectedConversation || !selectedTemplateId) return;

    setIsSending(true);
    setError("");

    try {
      const parameters = templateParameters
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

      await sendTemplate(selectedTemplateId, {
        contact_id: selectedConversation.contact,
        conversation_id: selectedConversation.id,
        parameters,
      });
      notify("success", "Template sent", "Your approved template was sent.");
      setSelectedTemplateId("");
      setTemplateParameters("");
      setActiveComposerPanel("");
      await loadConversations(filters, selectedConversation.id);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      const failedMessage = requestError.response?.data?.data;
      if (failedMessage) {
        setMessages((current) => [...current, failedMessage]);
      }
      setError(detail || "Unable to send template message.");
    } finally {
      setIsSending(false);
    }
  }

  function chooseMediaFile(event) {
    const file = event.target.files?.[0] || null;
    setMediaFile(file);
    setMediaMessageType(detectMediaType(file));
    setMediaProgress(0);
  }

  async function sendMediaMessage(event) {
    event.preventDefault();
    if (!selectedConversation || !mediaFile) return;

    setIsSending(true);
    setError("");
    setMediaProgress(0);

    try {
      const formData = new FormData();
      formData.append("file", mediaFile);
      formData.append("message_type", mediaMessageType);
      formData.append("caption", mediaCaption);

      await uploadMediaMessage(selectedConversation.id, formData, (progressEvent) => {
        if (!progressEvent.total) return;
        setMediaProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
      });

      notify("success", "Media sent", mediaFile.name);

      setMediaFile(null);
      setMediaCaption("");
      setMediaProgress(0);
      setActiveComposerPanel("");
      event.target.reset();
      await loadConversations(filters, selectedConversation.id);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail || requestError.response?.data?.message || requestError.response?.data?.file?.[0];
      const failedMessage = requestError.response?.data?.data;
      if (failedMessage) {
        setMessages((current) => [...current, failedMessage]);
      }
      setError(detail || "Unable to send media message.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className="inbox-page">
      <header className="dashboard-header inbox-page-header">
        <div className="inbox-title-group">
          <h1>Inbox</h1>
          <span
            aria-label={liveStatusLabel}
            className={isLiveConnected ? "inbox-status-dot inbox-status-dot--connected" : "inbox-status-dot"}
            role="status"
            title={liveStatusLabel}
          />
          <small>{conversations.filter((conversation) => conversation.status === "open").length} active conversations</small>
        </div>
        <div className="inbox-header-filters" aria-label="Conversation filters">
          {[['', 'All'], ['open', 'Open'], ['pending', 'Pending'], ['resolved', 'Resolved']].map(([value, label]) => (
            <button className={filters.status === value ? "inbox-filter-pill inbox-filter-pill--active" : "inbox-filter-pill"} key={label} onClick={() => updateFilter({ target: { name: "status", value } })} type="button">{label}</button>
          ))}
        </div>
      </header>

      {error ? <p className="form-error">{error}</p> : null}

      <div className={selectedConversation ? "inbox-layout inbox-layout--has-selection" : "inbox-layout"}>
        <aside className="inbox-sidebar crm-conversation-list">
          <div className="conversation-list-header"><div><h2>Conversations</h2><p>Sorted by latest activity</p></div><button aria-label="Start a new conversation" onClick={() => navigate("/contacts")} type="button"><Plus size={17}/></button></div>
          <div className="filters">
            <label className="conversation-search"><Search size={15}/><input aria-label="Search conversations" name="search" onChange={updateFilter} placeholder="Search conversations" type="search" value={filters.search}/></label>
            <div className="conversation-filter-chips">{[['', 'All'], ['open', 'Open'], ['pending', 'Pending'], ['resolved', 'Resolved']].map(([value, label]) => <button className={filters.status === value ? "active" : ""} key={label} onClick={() => updateFilter({ target: { name: "status", value } })} type="button">{label}</button>)}</div>
          </div>

          {isLoadingConversations ? <p>Loading conversations...</p> : null}
          {!isLoadingConversations && conversations.length === 0 ? (
            <p>No conversations yet. Start a chat from Contacts to begin.</p>
          ) : null}

          <div className="conversation-list">
            {conversations.map((conversation) => (
              <button
                className={
                  selectedConversation?.id === conversation.id
                    ? "conversation-item conversation-item--active"
                    : "conversation-item"
                }
                key={conversation.id}
                onClick={() => selectConversation(conversation)}
                type="button"
              >
                <span className="conversation-avatar"><UserRound aria-hidden="true" size={20} /></span>
                <span className="conversation-item__copy"><span className="conversation-item__title">{conversation.contact_name?.trim() || conversation.contact_phone || "Unknown contact"}</span><span className="conversation-item__preview">{conversation.last_message_preview || "No messages yet"}</span></span>
                <span className="conversation-item__meta"><time>{relativeTime(conversation.last_message_at || conversation.updated_at)}</time><i className={`conversation-item__status conversation-item__status--${conversation.status}`} title={conversation.status}/></span>
              </button>
            ))}
          </div>
        </aside>

        <main className="message-panel crm-chat-panel">
          {selectedConversation ? (
            <>
              <div className="message-header">
                <button className="inbox-back-button" aria-label="Back to conversations" onClick={returnToConversationList} type="button"><ArrowLeft size={18}/></button>
                <span className="message-header-avatar"><UserRound aria-hidden="true" size={20} /></span>
                <div className="message-header-copy">
                  <h2>{selectedConversation.contact_name || selectedConversation.contact_phone}</h2>
                  <p>{selectedConversation.contact_phone}</p>
                </div>
                <span className="pill">{selectedConversation.status}</span>
                <button ref={detailsTriggerRef} className="message-header-action" aria-label="Open customer details" aria-expanded={isDetailsOpen} onClick={() => setIsDetailsOpen(true)} type="button"><Info size={17}/></button>
              </div>

              <div className="message-history">
                {isLoadingMessages ? <p>Loading messages...</p> : null}
                {!isLoadingMessages && messages.length === 0 ? <p>No messages yet.</p> : null}
                {messages.map((message) => (
                  <div
                    className={
                      message.direction === "outbound"
                        ? "message-bubble message-bubble--outbound"
                        : "message-bubble message-bubble--inbound"
                    }
                    key={message.id}
                  >
                    {["image", "document", "audio", "video"].includes(message.message_type) ? (
                      <>
                        <MessageMedia message={message} />
                        {message.text ? <p>{message.text}</p> : null}
                      </>
                    ) : (
                      <p>{message.text || message.message_type}</p>
                    )}
                    <span>
                      {message.sender_type} - {formatTime(message.created_at)}
                    </span>
                    {message.direction === "outbound" ? (
                      <span className={`delivery-status delivery-status--${message.delivery_status}`}>
                        {message.delivery_status}
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>

              <div className="composer-dock">
                {activeComposerPanel === "template" ? (
                  <div className="composer-panel composer-panel--template">
                    <select
                      aria-label="Approved template"
                      onChange={(event) => setSelectedTemplateId(event.target.value)}
                      value={selectedTemplateId}
                    >
                      <option value="">Choose approved template</option>
                      {approvedTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name} ({template.language})
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label="Template parameters"
                      onChange={(event) => setTemplateParameters(event.target.value)}
                      placeholder="Parameters, comma separated"
                      type="text"
                      value={templateParameters}
                    />
                    <button className="button" disabled={isSending || !selectedTemplateId} onClick={sendSelectedTemplate} type="button">
                      <Send size={16} aria-hidden="true" />
                      Send Template
                    </button>
                  </div>
                ) : null}

                {activeComposerPanel === "media" ? (
                  <form className="composer-panel composer-panel--media" onSubmit={sendMediaMessage}>
                    <input aria-label="Media file" onChange={chooseMediaFile} type="file" />
                    <select
                      aria-label="Media type"
                      onChange={(event) => setMediaMessageType(event.target.value)}
                      value={mediaMessageType}
                    >
                      <option value="image">Image</option>
                      <option value="document">Document</option>
                      <option value="audio">Audio</option>
                      <option value="video">Video</option>
                    </select>
                    <input
                      aria-label="Media caption"
                      onChange={(event) => setMediaCaption(event.target.value)}
                      placeholder="Caption, optional"
                      type="text"
                      value={mediaCaption}
                    />
                    <button className="button" disabled={isSending || !mediaFile} type="submit">
                      <Send size={16} aria-hidden="true" />
                      {isSending && mediaFile ? `Uploading ${mediaProgress || 0}%` : "Send Media"}
                    </button>
                  </form>
                ) : null}

                <form className="composer" onSubmit={sendMessage}>
                  <div className="composer-tools">
                    <button
                      aria-pressed={activeComposerPanel === "template"}
                      className="icon-button composer-tool"
                      onClick={() => setActiveComposerPanel((current) => (current === "template" ? "" : "template"))}
                      type="button"
                    >
                      <FileText size={14} aria-hidden="true" />
                      Template
                    </button>
                    <button
                      aria-pressed={activeComposerPanel === "media"}
                      className="icon-button composer-tool"
                      onClick={() => setActiveComposerPanel((current) => (current === "media" ? "" : "media"))}
                      type="button"
                    >
                      <Image size={14} aria-hidden="true" />
                      Media
                    </button>
                  </div>
                  <textarea
                    aria-label="Message text"
                    onChange={(event) => setComposerText(event.target.value)}
                    placeholder="Write a message..."
                    rows="1"
                    value={composerText}
                  />
                  <button className="button button--primary" disabled={isSending} type="submit">
                    <Send size={16} aria-hidden="true" />
                    {isSending ? "Sending..." : "Send"}
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="empty-state">Select a conversation to view messages.</div>
          )}
        </main>

        {isDetailsOpen ? <button className="details-scrim" aria-label="Close customer details" onClick={() => { setIsDetailsOpen(false); requestAnimationFrame(() => detailsTriggerRef.current?.focus()); }} type="button" /> : null}
        <aside ref={detailsRef} tabIndex="-1" className={isDetailsOpen ? "details-panel crm-contact-panel is-open" : "details-panel crm-contact-panel"}>
          <div className="details-panel-header"><h2>Customer details</h2><button aria-label="Close customer details" onClick={() => { setIsDetailsOpen(false); requestAnimationFrame(() => detailsTriggerRef.current?.focus()); }} type="button">×</button></div>
          {selectedConversation ? (
            <>
              <div className="customer-summary"><span><UserRound aria-hidden="true" size={23} /></span><strong>{selectedConversation.contact_name || selectedConversation.contact_phone || "Unknown contact"}</strong><small>{selectedConversation.contact_phone}</small></div>
              <div className="customer-quick-actions">
                {selectedConversation.contact_phone ? <a href={`tel:${selectedConversation.contact_phone}`}>Call</a> : <span>Call</span>}
                {selectedConversation.contact_email ? <a href={`mailto:${selectedConversation.contact_email}`}>Email</a> : <span>Email</span>}
                <button aria-label="More customer actions" disabled type="button"><MoreHorizontal size={15}/> More</button>
              </div>
              <dl className="customer-overview">
                <div className="details-section-title">Overview</div>
                <dt>Status</dt><dd>{selectedConversation.status}</dd>
                <dt>Assigned to</dt><dd>{selectedConversation.assigned_to_email || "Unassigned"}</dd>
                <dt>Company</dt><dd>{selectedConversation.contact_company || "—"}</dd>
                <dt>Email</dt>
                <dd>{selectedConversation.contact_email || "—"}</dd>
              </dl>

              <label>
                Conversation status
                <select onChange={updateStatus} value={selectedConversation.status}>
                  <option value="open">Open</option>
                  <option value="pending">Pending</option>
                  <option value="resolved">Resolved</option>
                  <option value="closed">Closed</option>
                </select>
              </label>

              {role === "owner" || role === "admin" ? (
                <label>
                  Assigned agent
                  <select onChange={updateAssignedAgent} value={selectedConversation.assigned_to || ""}>
                    <option value="">Unassigned</option>
                    {members.map((member) => (
                      <option key={member.id} value={member.user}>
                        {member.email}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <form className="note-form details-tags-form" onSubmit={saveContactTags}>
                <div className="details-section-title">Tags</div>
                <label>
                  Contact tags
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

              <div className="tag-list">
                {(selectedConversation.contact_tags || []).map((tag) => (
                  <span className="tag-pill" key={tag.id} style={{ borderColor: tag.color }}>
                    {tag.name}
                  </span>
                ))}
              </div>

              <form className="note-form" onSubmit={addContactNote}>
                <div className="details-section-title">Contact note</div>
                <label>
                  Contact note
                  <textarea onChange={(event) => setContactNoteText(event.target.value)} rows="2" value={contactNoteText} />
                </label>
                <button className="button button--small" type="submit">Add Contact Note</button>
              </form>
              <div className="notes-list">
                {contactNotes.map((note) => (
                  <p key={note.id}>{note.note}</p>
                ))}
              </div>

              <form className="note-form" onSubmit={addConversationNote}>
                <div className="details-section-title">Conversation note</div>
                <label>
                  Conversation note
                  <textarea onChange={(event) => setConversationNoteText(event.target.value)} rows="2" value={conversationNoteText} />
                </label>
                <button className="button button--small" type="submit">Add Conversation Note</button>
              </form>
              <div className="notes-list">
                {conversationNotes.map((note) => (
                  <p key={note.id}>{note.note}</p>
                ))}
              </div>
            </>
          ) : (
            <p>No conversation selected.</p>
          )}
        </aside>
      </div>
    </section>
  );
}

export default Inbox;
