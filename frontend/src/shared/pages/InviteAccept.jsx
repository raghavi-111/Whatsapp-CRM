import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getCurrentUser, login, register } from "../services/authService.js";
import {
  acceptOrganizationInvitation,
  getOrganizationInvitation,
} from "../services/organizationService.js";
import { notify } from "../services/notificationService.js";
import { clearTokens, isLoggedIn } from "../services/tokenStorage.js";

/**
 * Invite Accept Page
 *
 * Public invitation route. Validates organization invite tokens and lets users
 * accept with an existing session or by authenticating/registering first.
 */

function getErrorMessage(error, fallback) {
  const data = error.response?.data;
  return data?.detail || data?.email?.[0] || data?.password?.[0] || data?.non_field_errors?.[0] || fallback;
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function InviteAccept() {
  const { token } = useParams();
  const navigate = useNavigate();

  // Invitation acceptance state coordinates invite lookup, auth, and final join action.
  const [invitation, setInvitation] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [formData, setFormData] = useState({ email: "", password: "" });
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadInvitation();
  }, [token]);

  async function loadInvitation() {
    setIsLoading(true);
    setError("");

    try {
      const inviteData = await getOrganizationInvitation(token);
      setInvitation(inviteData);
      setFormData((current) => ({ ...current, email: inviteData.email || "" }));

      if (isLoggedIn()) {
        try {
          const userData = await getCurrentUser();
          setCurrentUser(userData);
        } catch {
          clearTokens();
          setCurrentUser(null);
        }
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load this invitation."));
    } finally {
      setIsLoading(false);
    }
  }

  function updateField(event) {
    setFormData((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function canAttemptAccept(user = currentUser) {
    if (!invitation || !user) return false;
    return user.email.toLowerCase() === invitation.email.toLowerCase();
  }

  async function acceptInvite(user = currentUser) {
    if (!canAttemptAccept(user)) {
      setError(`Sign in as ${invitation.email} to accept this invitation.`);
      return;
    }

    setIsSubmitting(true);
    setError("");
    setMessage("");

    try {
      await acceptOrganizationInvitation(token);
      notify("success", "Invitation accepted", `You joined ${invitation.organization_name}.`);
      setMessage("Invitation accepted. Redirecting to dashboard...");
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to accept this invitation."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setMessage("");

    try {
      const authResponse = authMode === "login" ? await login(formData) : await register(formData);
      const user = authResponse.user;
      setCurrentUser(user);
      await acceptInvite(user);
    } catch (requestError) {
      setError(getErrorMessage(requestError, authMode === "login" ? "Unable to log in." : "Unable to register."));
    } finally {
      setIsSubmitting(false);
    }
  }

  const isFinalStatus = invitation && invitation.status !== "pending";
  const hasExpired = invitation?.is_expired || invitation?.status === "expired";
  const wrongEmail = currentUser && invitation && !canAttemptAccept();

  return (
    <section className="auth-page">
      <div className="auth-form">
        <h1>Accept invitation</h1>

        {isLoading ? <p>Loading invitation...</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
        {message ? <p className="form-success">{message}</p> : null}

        {invitation ? (
          <div className="invite-summary">
            <p>
              <strong>{invitation.organization_name}</strong> invited <strong>{invitation.email}</strong> as{" "}
              <strong>{invitation.role}</strong>.
            </p>
            <p>Status: {hasExpired ? "expired" : invitation.status}</p>
            <p>Expires: {formatDate(invitation.expires_at)}</p>
          </div>
        ) : null}

        {invitation && isFinalStatus ? (
          <p className="auth-note">This invitation is {invitation.status} and cannot be accepted.</p>
        ) : null}

        {invitation && !isFinalStatus && hasExpired ? (
          <p className="form-error">This invitation has expired.</p>
        ) : null}

        {invitation && !isFinalStatus && !hasExpired && currentUser ? (
          <>
            {wrongEmail ? (
              <p className="form-error">
                You are signed in as {currentUser.email}. This invitation belongs to {invitation.email}.
              </p>
            ) : (
              <p className="auth-note">Signed in as {currentUser.email}.</p>
            )}
            <div className="actions">
              <button
                className="button button--primary"
                disabled={isSubmitting || wrongEmail}
                onClick={() => acceptInvite()}
                type="button"
              >
                {isSubmitting ? "Accepting..." : "Accept Invitation"}
              </button>
              {wrongEmail ? (
                <button
                  className="button"
                  onClick={() => {
                    clearTokens();
                    setCurrentUser(null);
                    setError("");
                  }}
                  type="button"
                >
                  Sign in with invited email
                </button>
              ) : null}
            </div>
          </>
        ) : null}

        {invitation && !isFinalStatus && !hasExpired && !currentUser ? (
          <form onSubmit={submitAuth}>
            <label>
              Email
              <input
                autoComplete="email"
                name="email"
                onChange={updateField}
                required
                type="email"
                value={formData.email}
              />
            </label>
            <label>
              Password
              <input
                autoComplete={authMode === "login" ? "current-password" : "new-password"}
                minLength="8"
                name="password"
                onChange={updateField}
                required
                type="password"
                value={formData.password}
              />
            </label>
            <button className="button button--primary" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Working..." : authMode === "login" ? "Login and Accept" : "Register and Accept"}
            </button>
            <p className="auth-note">
              {authMode === "login" ? "Need an account?" : "Already have an account?"}{" "}
              <button
                className="link-button"
                onClick={() => {
                  setAuthMode(authMode === "login" ? "register" : "login");
                  setError("");
                }}
                type="button"
              >
                {authMode === "login" ? "Register instead" : "Login instead"}
              </button>
            </p>
          </form>
        ) : null}

        <p className="auth-note">
          <Link to="/login">Go to login</Link>
        </p>
      </div>
    </section>
  );
}

export default InviteAccept;
