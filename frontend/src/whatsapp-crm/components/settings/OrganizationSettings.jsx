import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";

/**
 * Organization Settings Panel
 *
 * Settings tab for workspace profile details and organization membership
 * visibility. It preserves role-aware member loading for owners/admins.
 */
import {
  getCurrentOrganization,
  getOrganizationMembers,
  updateCurrentOrganization,
} from "../../../shared/services/organizationService.js";
import { clearTokens } from "../../../shared/services/tokenStorage.js";
import { SettingsCard, SettingsGrid, SettingsSection } from "../../../shared/components/settings/SettingsLayout.jsx";

function OrganizationSettings({ embedded = false }) {
  const navigate = useNavigate();
  const { role = "agent" } = useOutletContext() || {};

  // Organization profile state and role-limited member summary.
  const [organization, setOrganization] = useState(null);
  const [members, setMembers] = useState([]);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let isMounted = true;

    // Load the organization profile and, for privileged users, its member list.
    getCurrentOrganization()
      .then(async (currentOrganization) => {
        const organizationMembers = role === "owner" || role === "admin" ? await getOrganizationMembers() : [];
        if (!isMounted) return;
        setOrganization(currentOrganization);
        setName(currentOrganization.name);
        setMembers(organizationMembers);
      })
      .catch((requestError) => {
        if (requestError.response?.status === 401) {
          clearTokens();
          if (isMounted) {
            navigate("/login", { replace: true });
          }
          return;
        }
        if (isMounted) {
          setError(requestError.response?.data?.detail || "Unable to load organization settings.");
        }
      });

    return () => {
      isMounted = false;
    };
  }, [navigate, role]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsSaving(true);

    try {
      const updatedOrganization = await updateCurrentOrganization({ name });
      setOrganization(updatedOrganization);
      setName(updatedOrganization.name);
      setMessage("Organization updated.");
    } catch (requestError) {
      setError(requestError.response?.data?.name?.[0] || "Unable to update organization.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className={embedded ? "settings-embedded-page" : "dashboard-page"}>
      {!embedded ? (
      <div className="dashboard-header">
        <div>
          <h1>Organization</h1>
        </div>
        <Link className="button" to="/dashboard">
          Dashboard
        </Link>
      </div>
      ) : null}

      <SettingsSection>
        <SettingsGrid className="settings-grid--profile">
          <SettingsCard as="form" className="settings-form settings-card--primary" onSubmit={handleSubmit}>
            <div className="settings-card__header">
              <div><h2>Current organization</h2><p>Update the workspace name shown throughout the CRM.</p></div>
            </div>
            {role === "agent" ? <p className="auth-note">Your role can view this page, but only owners and admins can update organization settings.</p> : null}

            <label>
              Organization name
              <input name="name" onChange={(event) => setName(event.target.value)} required type="text" value={name} />
            </label>

            {message ? <p className="form-success">{message}</p> : null}
            {error ? <p className="form-error">{error}</p> : null}

            <div className="settings-actions"><button className="button button--primary" disabled={isSaving || role === "agent"} type="submit">{isSaving ? "Saving..." : "Save Changes"}</button></div>
          </SettingsCard>

          <SettingsCard className="settings-summary-card">
            <div className="settings-card__header"><div><h2>Workspace summary</h2><p>Organization and access overview.</p></div></div>
            <dl className="settings-summary-list">
              <div><dt>Organization</dt><dd>{organization?.name || "Loading..."}</dd></div>
              <div><dt>Your role</dt><dd className="pill">{role}</dd></div>
              <div><dt>Visible members</dt><dd>{members.length}</dd></div>
            </dl>
          </SettingsCard>
        </SettingsGrid>

        {role === "owner" || role === "admin" ? (
          <SettingsCard>
            <div className="settings-card__header"><div><h2>Members</h2><p>People with access to this workspace.</p></div><span className="pill">{members.length} total</span></div>
            <div className="members-list">{members.map((member) => <div className="member-row" key={member.id}><span>{member.email}</span><span>{member.role}</span><span className={`pill pill--${member.status}`}>{member.status}</span></div>)}</div>
          </SettingsCard>
        ) : null}
      </SettingsSection>
    </section>
  );
}

export default OrganizationSettings;
