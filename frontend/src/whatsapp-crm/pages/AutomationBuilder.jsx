import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { FileAudio, FileText, Film, Image, Save, Trash2, X } from "lucide-react";

import { createAutomation, getAutomationMedia, uploadAutomationMedia } from "../services/automationService.js";
import { getOrganizationMembers } from "../../shared/services/organizationService.js";
import { getTags } from "../services/supportService.js";
import { getTemplates } from "../services/templateService.js";
import { clearTokens } from "../../shared/services/tokenStorage.js";

const triggerOptions = [
  ["inbound_message_received", "New inbound WhatsApp message"],
  ["contact_created", "New contact created"],
  ["tag_added", "Contact tag added"],
  ["conversation_status_changed", "Conversation status changed"],
  ["deal_created", "Deal created"],
  ["deal_stage_changed", "Deal stage changed"],
  ["broadcast_completed", "Broadcast completed"],
];

const conditionFields = [
  ["message_text_contains", "Message contains keyword"],
  ["message_text_equals", "Message equals text"],
  ["message_text_starts_with", "Message starts with"],
  ["message_text_ends_with", "Message ends with"],
  ["contact_has_tag", "Contact has tag"],
  ["contact_does_not_have_tag", "Contact does not have tag"],
  ["contact_source", "Contact source"],
  ["contact_status", "Contact status"],
  ["conversation_status", "Conversation status"],
  ["deal_stage", "Deal stage"],
  ["business_hours", "Business hours"],
  ["assigned_user", "Assigned user"],
  ["first_message", "First inbound message"],
];

const actionTypes = [
  ["send_message", "Send WhatsApp text reply"],
  ["send_template", "Send approved template"],
  ["send_image", "Send WhatsApp image"],
  ["send_document", "Send WhatsApp document/PDF"],
  ["send_brochure", "Send WhatsApp brochure"],
  ["send_video", "Send WhatsApp video"],
  ["send_audio", "Send WhatsApp audio"],
  ["send_media", "Send WhatsApp media with caption"],
  ["add_tag", "Add tag"],
  ["remove_tag", "Remove tag"],
  ["create_deal", "Create deal if missing"],
  ["update_deal_stage", "Update deal stage"],
  ["assign_agent", "Assign conversation"],
  ["create_notification", "Create internal notification"],
  ["add_contact_note", "Add contact note"],
  ["update_conversation_status", "Change conversation status"],
  ["stop", "Stop automation"],
];

const mediaActions = ["send_image", "send_document", "send_brochure", "send_video", "send_audio", "send_media"];
const mediaConfig = {
  image: { accept: ".jpg,.jpeg,.png,.webp", limit: 5, label: "JPG, PNG or WebP" },
  document: { accept: ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx", limit: 100, label: "PDF, Word, Excel or PowerPoint" },
  video: { accept: ".mp4", limit: 16, label: "MP4" },
  audio: { accept: ".mp3,.ogg,.m4a", limit: 16, label: "MP3, OGG or M4A" },
};
function actionMediaType(action) { return ({ send_image: "image", send_document: "document", send_brochure: "document", send_video: "video", send_audio: "audio" })[action.type] || action.media_type || "image"; }

const emptyCondition = { field: "message_text_contains", operator: "icontains", value: "" };
const emptyAction = { type: "send_message", text: "" };

function cloneList(value, fallback) {
  if (!Array.isArray(value) || value.length === 0) return fallback;
  return JSON.parse(JSON.stringify(value));
}

function extractTemplateVariables(template) {
  const matches = [...(template?.body_text || "").matchAll(/{{\s*(\d+)\s*}}/g)].map((match) => Number(match[1]));
  return Array.from({ length: Math.max(0, ...matches) }, (_, index) => index + 1);
}

function normalizeAction(type) {
  if (type === "send_message") return { type, text: "" };
  if (type === "send_template") return { type, template_id: "", parameter_mappings: [] };
  if (mediaActions.includes(type)) return { type, media_type: type === "send_media" ? "image" : actionMediaType({ type }), media_source: "library", media_id: "", filename: "", mime_type: "", caption: "" };
  if (type === "add_tag" || type === "remove_tag") return { type, tag_name: "" };
  if (type === "create_deal") return { type, stage: "New" };
  if (type === "update_deal_stage") return { type, stage: "Qualified", create_if_missing: true };
  if (type === "assign_agent") return { type, agent_id: "" };
  if (type === "create_notification") return { type, message: "" };
  if (type === "add_contact_note") return { type, note: "" };
  if (type === "update_conversation_status") return { type, status: "pending" };
  return { type };
}

function AutomationBuilder() {
  const location = useLocation();
  const navigate = useNavigate();
  const sourceTemplate = location.state?.template || null;

  const [name, setName] = useState(sourceTemplate?.name || "");
  const [description, setDescription] = useState(sourceTemplate?.description || "");
  const [triggerType, setTriggerType] = useState(sourceTemplate?.trigger_type || "inbound_message_received");
  const [conditionLogic, setConditionLogic] = useState(sourceTemplate?.condition_logic || "and");
  const [isActive, setIsActive] = useState(false);
  const [conditions, setConditions] = useState(() => cloneList(sourceTemplate?.conditions_json, [emptyCondition]));
  const [actions, setActions] = useState(() => cloneList(sourceTemplate?.actions_json, [emptyAction]));
  const [templates, setTemplates] = useState([]);
  const [tags, setTags] = useState([]);
  const [members, setMembers] = useState([]);
  const [media, setMedia] = useState([]);
  const [uploadingAction, setUploadingAction] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadBuilderData();
  }, []);

  const approvedTemplates = useMemo(() => templates.filter((template) => template.status === "approved"), [templates]);

  async function loadBuilderData() {
    try {
      const [templateData, tagData, memberData, mediaData] = await Promise.all([
        getTemplates({ status: "approved" }),
        getTags(),
        getOrganizationMembers(),
        getAutomationMedia(),
      ]);
      setTemplates(templateData);
      setTags(tagData);
      setMembers(memberData.filter((member) => member.status === "active"));
      setMedia(mediaData);
    } catch {
      setError("Unable to load builder options.");
    }
  }

  async function handleMediaUpload(index, file) {
    if (!file) return;
    const type = actionMediaType(actions[index]);
    const config = mediaConfig[type];
    if (file.size > config.limit * 1024 * 1024) return setError(`${type} files must be ${config.limit}MB or smaller.`);
    setUploadingAction(index);
    setError("");
    try {
      const item = await uploadAutomationMedia(file, type);
      setMedia((current) => [item, ...current]);
      setActions((current) => current.map((action, itemIndex) => itemIndex === index ? { ...action, media_source: "library", media_id: item.id, file_url: "", filename: item.filename, mime_type: item.mime_type } : action));
    } catch (uploadError) {
      setError(uploadError.response?.data?.detail || "Unable to upload media.");
    } finally {
      setUploadingAction(null);
    }
  }

  function updateCondition(index, field, value) {
    setConditions((current) => current.map((condition, itemIndex) => (
      itemIndex === index ? { ...condition, [field]: value } : condition
    )));
  }

  function updateAction(index, field, value) {
    setActions((current) => current.map((action, itemIndex) => {
      if (itemIndex !== index) return action;
      if (field === "type") return normalizeAction(value);
      return { ...action, [field]: value };
    }));
  }

  function updateTemplateAction(index, templateId) {
    const template = approvedTemplates.find((item) => String(item.id) === String(templateId));
    const parameter_mappings = extractTemplateVariables(template).map(() => ({ type: "contact_name", value: "" }));
    setActions((current) => current.map((action, itemIndex) => (
      itemIndex === index
        ? { ...action, template_id: Number(templateId), language: template?.language || "", parameter_mappings }
        : action
    )));
  }

  function updateParameterMapping(actionIndex, mappingIndex, field, value) {
    setActions((current) => current.map((action, itemIndex) => {
      if (itemIndex !== actionIndex) return action;
      const mappings = [...(action.parameter_mappings || [])];
      mappings[mappingIndex] = { ...mappings[mappingIndex], [field]: value };
      return { ...action, parameter_mappings: mappings };
    }));
  }

  function moveAction(index, direction) {
    setActions((current) => {
      const next = [...current];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  async function saveAutomation(activateRule) {
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      if (!name.trim()) {
        throw new Error("Automation name is required.");
      }

      await createAutomation({
        name: name.trim(),
        description,
        trigger_type: triggerType,
        condition_logic: conditionLogic,
        conditions_json: conditions.filter((condition) => condition.field === "first_message" || condition.field === "business_hours" || String(condition.value || "").trim()),
        actions_json: actions,
        is_active: activateRule,
      });
      setIsActive(activateRule);
      setMessage(activateRule ? "Automation saved and activated." : "Draft automation saved.");
      window.setTimeout(() => navigate("/automations"), 700);
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        clearTokens();
        navigate("/login", { replace: true });
        return;
      }
      setError(requestError.response?.data?.detail || requestError.response?.data?.actions_json?.[0] || requestError.response?.data?.conditions_json?.[0] || requestError.message || "Unable to save automation.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="builder-page">
      <header className="builder-topbar">
        <Link className="button button--small" to="/automations">Back</Link>
        <div className="builder-title-group">
          {sourceTemplate ? <span className="builder-template-context">Created from template: {sourceTemplate.name}</span> : null}
          <label className="builder-name-label">
            Automation name
            <input
              aria-label="Automation name"
              className="builder-title-input"
              onChange={(event) => setName(event.target.value)}
              placeholder="Name this automation"
              value={name}
            />
          </label>
        </div>
        <label className="toggle-label">
          Active
          <input checked={isActive} onChange={(event) => setIsActive(event.target.checked)} type="checkbox" />
        </label>
        <button className="button" disabled={isSaving} onClick={() => saveAutomation(false)} type="button">
          <Save size={16} aria-hidden="true" />
          {isSaving ? "Saving..." : "Save Draft"}
        </button>
        <button className="button button--primary" disabled={isSaving} onClick={() => saveAutomation(true)} type="button">
          <Save size={16} aria-hidden="true" />
          {isSaving ? "Saving..." : "Save & Activate"}
        </button>
        <Link className="button" to="/automations">
          <X size={16} aria-hidden="true" />
          Cancel
        </Link>
      </header>

      <div className="builder-canvas automation-builder-canvas">
        <article className="builder-node automation-builder-node automation-builder-node--summary">
          <span>Step 1</span>
          <h2>Basic info</h2>
          <p>Name the automation, choose whether it should start active, then configure the workflow below.</p>
        </article>

        <article className="builder-node automation-builder-node">
          <span>Step 2</span>
          <h2>Trigger</h2>
          <label>
            Trigger type
            <select onChange={(event) => setTriggerType(event.target.value)} value={triggerType}>
              {triggerOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>
            Description
            <textarea onChange={(event) => setDescription(event.target.value)} rows="2" value={description} />
          </label>
        </article>

        <article className="builder-node automation-builder-node">
          <span>Step 3</span>
          <h2>Conditions</h2>
          <label>
            Logic
            <select onChange={(event) => setConditionLogic(event.target.value)} value={conditionLogic}>
              <option value="and">All conditions must match</option>
              <option value="or">Any condition can match</option>
            </select>
          </label>
          {conditions.map((condition, index) => (
            <div className="automation-builder-row" key={`${condition.field}-${index}`}>
              <select onChange={(event) => updateCondition(index, "field", event.target.value)} value={condition.field}>
                {conditionFields.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <input
                disabled={["first_message", "business_hours"].includes(condition.field)}
                onChange={(event) => updateCondition(index, "value", event.target.value)}
                placeholder="Value"
                value={condition.value || ""}
              />
              <button className="button button--small" onClick={() => setConditions((current) => current.filter((_, itemIndex) => itemIndex !== index))} type="button">Remove</button>
            </div>
          ))}
          <button className="button" onClick={() => setConditions((current) => [...current, emptyCondition])} type="button">Add Condition</button>
        </article>

        <article className="builder-node automation-builder-node">
          <span>Step 4</span>
          <h2>Actions</h2>
          {actions.map((action, index) => {
            const template = approvedTemplates.find((item) => String(item.id) === String(action.template_id));
            const variables = extractTemplateVariables(template);
            return (
              <div className="automation-action-editor" key={`${action.type}-${index}`}>
                <div className="automation-builder-row">
                  <select onChange={(event) => updateAction(index, "type", event.target.value)} value={action.type}>
                    {actionTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                  <button className="button button--small" disabled={index === 0} onClick={() => moveAction(index, -1)} type="button">Up</button>
                  <button className="button button--small" disabled={index === actions.length - 1} onClick={() => moveAction(index, 1)} type="button">Down</button>
                  <button className="button button--small" onClick={() => setActions((current) => current.filter((_, itemIndex) => itemIndex !== index))} type="button">Remove</button>
                </div>

                {action.type === "send_message" ? <textarea onChange={(event) => updateAction(index, "text", event.target.value)} placeholder="Reply text" rows="2" value={action.text || ""} /> : null}
                {mediaActions.includes(action.type) ? (() => {
                  const type = actionMediaType(action);
                  const config = mediaConfig[type];
                  const selected = media.find((item) => String(item.id) === String(action.media_id));
                  const Icon = type === "image" ? Image : type === "video" ? Film : type === "audio" ? FileAudio : FileText;
                  const clearMedia = () => setActions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, media_id: "", file_url: "", filename: "", mime_type: "" } : item));
                  return <div className="automation-media-action">
                    {action.type === "send_media" ? <label>Media type<select onChange={(event) => setActions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, media_type: event.target.value, media_id: "", filename: "", mime_type: "" } : item))} value={type}><option value="image">Image</option><option value="document">Document</option><option value="video">Video</option><option value="audio">Audio</option></select></label> : null}
                    <label>Media source<select onChange={(event) => updateAction(index, "media_source", event.target.value)} value={action.media_source || "library"}><option value="library">Upload / media library</option><option value="url">Public HTTPS URL</option></select></label>
                    {action.media_source === "url" ? <label>Public media URL<input onChange={(event) => updateAction(index, "file_url", event.target.value)} placeholder="https://example.com/file.pdf" type="url" value={action.file_url || ""} /></label> : <>
                      <label>Existing media<select onChange={(event) => { const item = media.find((entry) => String(entry.id) === event.target.value); setActions((current) => current.map((entry, itemIndex) => itemIndex === index ? { ...entry, media_id: item?.id || "", filename: item?.filename || "", mime_type: item?.mime_type || "", file_url: "" } : entry)); }} value={action.media_id || ""}><option value="">Select from library</option>{media.filter((item) => item.media_type === type).map((item) => <option key={item.id} value={item.id}>{item.filename}</option>)}</select></label>
                      <label className="automation-media-upload">Upload / replace<input accept={config.accept} disabled={uploadingAction === index} onChange={(event) => handleMediaUpload(index, event.target.files?.[0])} type="file" /><small>{config.label}, up to {config.limit}MB</small></label>
                    </>}
                    <label>Filename<input onChange={(event) => updateAction(index, "filename", event.target.value)} placeholder="Customer-visible filename" value={action.filename || ""} /></label>
                    {type !== "audio" ? <label>Caption<textarea maxLength="1024" onChange={(event) => updateAction(index, "caption", event.target.value)} placeholder="Optional caption" rows="2" value={action.caption || ""} /></label> : null}
                    {(selected || action.file_url) ? <div className="automation-media-preview"><Icon aria-hidden="true" size={28} />{type === "image" && selected?.file_url ? <img alt="Selected media preview" src={selected.file_url} /> : null}<div><strong>{action.filename || selected?.filename || action.file_url}</strong><small>{action.mime_type || selected?.mime_type || type}</small></div><button aria-label="Remove selected media" className="button button--small" onClick={clearMedia} type="button"><Trash2 size={15} /></button></div> : null}
                  </div>;
                })() : null}
                {["add_tag", "remove_tag"].includes(action.type) ? (
                  <input list="automation-tags" onChange={(event) => updateAction(index, "tag_name", event.target.value)} placeholder="Tag name" value={action.tag_name || ""} />
                ) : null}
                {action.type === "send_template" ? (
                  <div className="automation-template-action">
                    <select onChange={(event) => updateTemplateAction(index, event.target.value)} value={action.template_id || ""}>
                      <option value="">Select approved template</option>
                      {approvedTemplates.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.language})</option>)}
                    </select>
                    {variables.map((variable, mappingIndex) => (
                      <div className="automation-builder-row" key={variable}>
                        <strong>{`{{${variable}}}`}</strong>
                        <select onChange={(event) => updateParameterMapping(index, mappingIndex, "type", event.target.value)} value={action.parameter_mappings?.[mappingIndex]?.type || "contact_name"}>
                          <option value="contact_name">Contact name</option>
                          <option value="phone_number">Phone number</option>
                          <option value="company">Company</option>
                          <option value="message_text">Message text</option>
                          <option value="static">Static text</option>
                        </select>
                        {action.parameter_mappings?.[mappingIndex]?.type === "static" ? (
                          <input onChange={(event) => updateParameterMapping(index, mappingIndex, "value", event.target.value)} placeholder="Static text" value={action.parameter_mappings?.[mappingIndex]?.value || ""} />
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}
                {["create_deal", "update_deal_stage"].includes(action.type) ? (
                  <select onChange={(event) => updateAction(index, "stage", event.target.value)} value={action.stage || "New"}>
                    <option value="New">New</option>
                    <option value="Qualified">Qualified</option>
                    <option value="Proposal">Proposal</option>
                    <option value="Won">Won</option>
                  </select>
                ) : null}
                {action.type === "assign_agent" ? (
                  <select onChange={(event) => updateAction(index, "agent_id", Number(event.target.value))} value={action.agent_id || ""}>
                    <option value="">Select team member</option>
                    {members.map((member) => <option key={member.user} value={member.user}>{member.email}</option>)}
                  </select>
                ) : null}
                {action.type === "create_notification" ? <input onChange={(event) => updateAction(index, "message", event.target.value)} placeholder="Notification message" value={action.message || ""} /> : null}
                {action.type === "add_contact_note" ? <textarea onChange={(event) => updateAction(index, "note", event.target.value)} placeholder="Contact note" rows="2" value={action.note || ""} /> : null}
                {action.type === "update_conversation_status" ? (
                  <select onChange={(event) => updateAction(index, "status", event.target.value)} value={action.status || "pending"}>
                    <option value="open">Open</option>
                    <option value="pending">Pending</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>
                ) : null}
              </div>
            );
          })}
          <button className="button" onClick={() => setActions((current) => [...current, emptyAction])} type="button">Add Action</button>
        </article>

        <article className="builder-node automation-builder-node automation-builder-node--summary">
          <span>Step 5</span>
          <h2>Review & Save</h2>
          <dl className="builder-review-list">
            <div><dt>Name</dt><dd>{name.trim() || "Not named yet"}</dd></div>
            <div><dt>Status</dt><dd>{isActive ? "Active after save" : "Draft until activated"}</dd></div>
            <div><dt>Trigger</dt><dd>{triggerType}</dd></div>
            <div><dt>Conditions</dt><dd>{conditions.length}</dd></div>
            <div><dt>Actions</dt><dd>{actions.length}</dd></div>
          </dl>
          <p>Use Save Draft to keep this inactive, or Save & Activate when it is ready to run.</p>
        </article>

        <datalist id="automation-tags">
          {tags.map((tag) => <option key={tag.id} value={tag.name} />)}
        </datalist>

        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </div>
    </section>
  );
}

export default AutomationBuilder;
