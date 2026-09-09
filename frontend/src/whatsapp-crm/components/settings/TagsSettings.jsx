import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

/**
 * Tags Settings Panel
 *
 * Manages CRM contact/conversation tags inside the Settings tab shell.
 * Keeps tag CRUD local to this feature panel while using shared support APIs.
 */
import { createTag, deleteTag, getTags, updateTag } from "../../services/supportService.js";
import { SettingsCard, SettingsSection, SettingsTableWrapper } from "../../../shared/components/settings/SettingsLayout.jsx";

const emptyTag = { name: "", color: "#128c7e" };

function TagsSettings({ embedded = false }) {
  // Tag editor state supports both create and inline edit modes.
  const [tags, setTags] = useState([]);
  const [formData, setFormData] = useState(emptyTag);
  const [editingTagId, setEditingTagId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadTags();
  }, []);

  async function loadTags() {
    try {
      setTags(await getTags());
    } catch {
      setError("Unable to load tags.");
    }
  }

  function updateField(event) {
    setFormData((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function startEdit(tag) {
    setEditingTagId(tag.id);
    setFormData({ name: tag.name, color: tag.color });
    setMessage("");
    setError("");
  }

  function resetForm() {
    setEditingTagId(null);
    setFormData(emptyTag);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      if (editingTagId) {
        await updateTag(editingTagId, formData);
        setMessage("Tag updated.");
      } else {
        await createTag(formData);
        setMessage("Tag created.");
      }
      resetForm();
      await loadTags();
    } catch (requestError) {
      setError(requestError.response?.data?.name?.[0] || "Unable to save tag.");
    }
  }

  async function handleDelete(tag) {
    if (!window.confirm(`Delete tag ${tag.name}?`)) return;
    try {
      await deleteTag(tag.id);
      setMessage("Tag deleted.");
      await loadTags();
    } catch {
      setError("Unable to delete tag.");
    }
  }

  return (
    <section className={embedded ? "settings-embedded-page" : "dashboard-page"}>
      {!embedded ? (
      <div className="dashboard-header">
        <div>
          <h1>Tags</h1>
        </div>
        <Link className="button" to="/dashboard">Dashboard</Link>
      </div>
      ) : null}

      <SettingsSection>
      <SettingsCard as="form" className="settings-form tag-editor-card" onSubmit={handleSubmit}>
        <div className="settings-card__header"><div><h2>{editingTagId ? "Edit tag" : "Create tag"}</h2><p>Create reusable labels for contacts and conversations.</p></div></div>
        <div className="tag-editor-card__grid">
          <label>
            Name
            <input name="name" onChange={updateField} required value={formData.name} />
          </label>
          <label>
            Color
            <span className="tag-color-control">
              <span className="tag-color-swatch" style={{ background: formData.color }} />
              <input aria-label="Tag color" name="color" onChange={updateField} type="color" value={formData.color} />
            </span>
          </label>
          <label>Hex code<input aria-label="Tag hex code" name="color" onChange={updateField} type="text" value={formData.color} /></label>
          <button className="button button--primary" type="submit">{editingTagId ? "Update Tag" : "Create Tag"}</button>
        </div>
        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
        {editingTagId ? (
        <div className="actions">
          <button className="button" onClick={resetForm} type="button">Cancel</button>
        </div>
        ) : null}
      </SettingsCard>

      <SettingsCard className="contacts-panel tags-list-panel settings-table-card">
        <div className="settings-card__header"><div><h2>Tags</h2><p>Manage the labels available across the workspace.</p></div><span className="pill">{tags.length} total</span></div>
        {tags.length === 0 ? <p>No tags yet.</p> : null}
        <SettingsTableWrapper className="tags-table-scroll">
          <table className="contacts-table tags-table">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Color</th>
                <th>Hex Code</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tags.map((tag) => (
                <tr key={tag.id}>
                  <td>
                    <span className="tag-name-cell">
                      <span className="tag-dot" style={{ background: tag.color }} />
                      {tag.name}
                    </span>
                  </td>
                  <td>
                    <span className="tag-color-swatch tag-color-swatch--table" style={{ background: tag.color }} />
                  </td>
                  <td><code>{tag.color}</code></td>
                  <td>
                    <span className="row-actions tags-table__actions">
                      <button className="button button--small" onClick={() => startEdit(tag)} type="button">Edit</button>
                      <button className="button button--small" onClick={() => handleDelete(tag)} type="button">Delete</button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SettingsTableWrapper>
      </SettingsCard>
      </SettingsSection>
    </section>
  );
}

export default TagsSettings;
