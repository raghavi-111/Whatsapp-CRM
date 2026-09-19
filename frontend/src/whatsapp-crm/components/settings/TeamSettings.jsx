import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

/**
 * Team Settings Panel
 *
 * Handles organization members and invitation links for Settings > Team.
 * Invitation URLs are generated for development/local acceptance flows.
 */
import { getCurrentUser } from "../../../shared/services/authService.js";
import {
  cancelOrganizationInvitation,
  createOrganizationInvitation,
  getOrganizationInvitations,
  getOrganizationMembers,
  removeOrganizationMember,
  updateOrganizationMember,
} from "../../../shared/services/organizationService.js";
import { clearTokens } from "../../../shared/services/tokenStorage.js";
import { notify } from "../../../shared/services/notificationService.js";
import { SettingsCard, SettingsSection, SettingsTableWrapper } from "../../../shared/components/settings/SettingsLayout.jsx";

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function getErrorMessage(error, fallback) {
  const data = error.response?.data;
  return data?.detail || data?.email?.[0] || data?.role?.[0] || data?.non_field_errors?.[0] || fallback;
}

function getInvitationAcceptUrl(invitation) {
  if (!invitation?.token) return invitation?.accept_url || "";
  return `${window.location.origin}/invite/accept/${invitation.token}`;
}

function TeamSettings({ embedded = false }) {
  const navigate = useNavigate();

  // Team management state: current user permissions, members, and invitations.
  const [user, setUser] = useState(null);
  const [members, setMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [inviteForm, setInviteForm] = useState({ email: "", role: "agent" });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const currentMember = useMemo(
    () => members.find((member) => member.user === user?.id) || null,
    [members, user],
  );
  const canManageAdmins = currentMember?.role === "owner";
  const canManageTeam = currentMember?.role === "owner" || currentMember?.role === "admin";

  useEffect(() => {
    loadTeam();
  }, []);

  async function loadTeam() {
    setIsLoading(true);
    setError("");

    try {
      const [currentUser, memberData, invitationData] = await Promise.all([
        getCurrentUser(),
        getOrganizationMembers(),
        getOrganizationInvitations(),
      ]);
      setUser(currentUser);
      setMembers(memberData);
      setInvitations(invitationData);
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        clearTokens();
        navigate("/login", { replace: true });
        return;
      }
      setError(getErrorMessage(requestError, "Unable to load team settings."));
    } finally {
      setIsLoading(false);
    }
  }

  function updateInviteForm(event) {
    setInviteForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function submitInvitation(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      await createOrganizationInvitation(inviteForm);
      setInviteForm({ email: "", role: "agent" });
      setMessage("Invitation created.");
      await loadTeam();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to create invitation."));
    } finally {
      setIsSaving(false);
    }
  }

  async function changeMemberRole(member, role) {
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      await updateOrganizationMember(member.id, { role });
      setMessage("Member role updated.");
      await loadTeam();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to update member role."));
    } finally {
      setIsSaving(false);
    }
  }

  async function disableMember(member) {
    const confirmed = window.confirm(`Remove ${member.email} from this organization?`);
    if (!confirmed) return;

    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      await removeOrganizationMember(member.id);
      setMessage("Member removed.");
      await loadTeam();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to remove member."));
    } finally {
      setIsSaving(false);
    }
  }

  async function cancelInvitation(invitation) {
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      await cancelOrganizationInvitation(invitation.id);
      setMessage("Invitation cancelled.");
      await loadTeam();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to cancel invitation."));
    } finally {
      setIsSaving(false);
    }
  }

  async function copyInvitationLink(invitation) {
    const url = getInvitationAcceptUrl(invitation);
    if (!url) return;

    try {
      await navigator.clipboard.writeText(url);
      setMessage("Invitation link copied.");
      notify("success", "Copied", "Invitation link copied to clipboard.");
    } catch {
      setError("Unable to copy invitation link.");
      notify("error", "Copy failed", "Unable to copy invitation link.");
    }
  }

  function openInvitationLink(invitation) {
    const url = getInvitationAcceptUrl(invitation);
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function canEditMember(member) {
    if (!canManageTeam) return false;
    if (currentMember?.role === "owner") return member.user !== user?.id;
    return member.role === "agent";
  }

  return (
    <section className={embedded ? "settings-embedded-page" : "dashboard-page"}>
      {!embedded ? (
      <div className="dashboard-header">
        <div>
          <h1>Team</h1>
        </div>
        <Link className="button" to="/dashboard">
          Dashboard
        </Link>
      </div>
      ) : null}

      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="form-success">{message}</p> : null}
      {isLoading ? <p>Loading team...</p> : null}

      {!isLoading && canManageTeam ? (
        <SettingsSection>
          <SettingsCard as="form" className="contact-form team-invite-card" onSubmit={submitInvitation}>
            <div className="settings-card__header"><div><h2>Invite member</h2><p>Invite a teammate and assign their initial workspace role.</p></div></div>
            <div className="team-invite-card__grid">
              <label>
                Email
                <input name="email" onChange={updateInviteForm} required type="email" value={inviteForm.email} />
              </label>
              <label>
                Role
                <select name="role" onChange={updateInviteForm} value={inviteForm.role}>
                  {canManageAdmins ? <option value="admin">Admin</option> : null}
                  <option value="agent">Agent</option>
                </select>
              </label>
              <button className="button button--primary" disabled={isSaving} type="submit">
                {isSaving ? "Saving..." : "Create Invitation"}
              </button>
            </div>
          </SettingsCard>

          <SettingsCard className="contacts-panel settings-table-card">
            <div className="settings-card__header"><div><h2>Members</h2><p>Active workspace members and role assignments.</p></div><span className="pill">{members.length} total</span></div>
            <SettingsTableWrapper>
              <table className="contacts-table team-members-table">
                <colgroup>
                  <col className="team-column--email" />
                  <col className="team-column--role" />
                  <col className="team-column--status" />
                  <col className="team-column--date" />
                  <col className="team-column--member-actions" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Joined At</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((member) => (
                    <tr key={member.id}>
                      <td className="team-email-cell"><span title={member.email}>{member.email}</span></td>
                      <td>{member.role}</td>
                      <td><span className={`pill pill--${member.status}`}>{member.status}</span></td>
                      <td>{formatDate(member.joined_at)}</td>
                      <td>
                        <div className="row-actions">
                          {canEditMember(member) ? (
                            <>
                              <select
                                aria-label={`Role for ${member.email}`}
                                disabled={isSaving}
                                onChange={(event) => changeMemberRole(member, event.target.value)}
                                value={member.role}
                              >
                                {canManageAdmins ? <option value="owner">Owner</option> : null}
                                {canManageAdmins ? <option value="admin">Admin</option> : null}
                                <option value="agent">Agent</option>
                              </select>
                              <button className="button button--small" disabled={isSaving} onClick={() => disableMember(member)} type="button">
                                Remove
                              </button>
                            </>
                          ) : (
                            <span className="auth-note">No actions</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </SettingsTableWrapper>
          </SettingsCard>

          <SettingsCard className="contacts-panel team-invitations-panel settings-table-card">
            <div className="settings-card__header"><div><h2>Pending invitations</h2><p>Track and manage invitations that have been issued.</p></div><span className="pill">{invitations.length} total</span></div>
            {invitations.length === 0 ? <p>No invitations yet.</p> : null}
            {invitations.length > 0 ? (
              <SettingsTableWrapper className="team-table-scroll">
                <table className="contacts-table team-invitations-table">
                  <colgroup>
                    <col className="team-column--email" />
                    <col className="team-column--role" />
                    <col className="team-column--status" />
                    <col className="team-column--date" />
                    <col className="team-column--link" />
                    <col className="team-column--invitation-actions" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Expires At</th>
                      <th>Link</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invitations.map((invitation) => (
                      <tr key={invitation.id}>
                        <td className="team-email-cell"><span title={invitation.email}>{invitation.email}</span></td>
                        <td>{invitation.role}</td>
                        <td>
                          <span className={`pill pill--${invitation.status}`}>{invitation.status}</span>
                        </td>
                        <td>{formatDate(invitation.expires_at)}</td>
                        <td>
                          <div
                            className="invitation-link-cell"
                            onDoubleClick={() => openInvitationLink(invitation)}
                            title="Double-click to open invitation link"
                          >
                            <button className="link-button invitation-link-label" type="button">
                              Invitation Link
                            </button>
                            <button
                              className="button button--small"
                              onClick={() => copyInvitationLink(invitation)}
                              type="button"
                            >
                              Copy
                            </button>
                          </div>
                        </td>
                        <td>
                          {invitation.status === "pending" ? (
                            <button className="button button--small" disabled={isSaving} onClick={() => cancelInvitation(invitation)} type="button">
                              Cancel
                            </button>
                          ) : (
                            <span className="auth-note">No actions</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </SettingsTableWrapper>
            ) : null}
          </SettingsCard>
        </SettingsSection>
      ) : null}
    </section>
  );
}

export default TeamSettings;
