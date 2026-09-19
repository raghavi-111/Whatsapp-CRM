import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

/**
 * WhatsApp Settings Panel
 *
 * Stores organization-level Meta/WhatsApp Cloud API credentials and webhook
 * setup hints. Secret values remain in state only for form submission.
 */
import {
  createWhatsAppConfig,
  getWhatsAppConfig,
  testWhatsAppConnection,
  updateWhatsAppConfig,
} from "../../services/whatsappService.js";
import { clearTokens } from "../../../shared/services/tokenStorage.js";
import { SettingsCard, SettingsGrid, SettingsSection } from "../../../shared/components/settings/SettingsLayout.jsx";

const emptyConfig = {
  business_name: "",
  phone_number: "",
  phone_number_id: "",
  whatsapp_business_account_id: "",
  meta_app_id: "",
  meta_app_secret: "",
  access_token: "",
  webhook_verify_token: "",
  is_active: true,
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
const publicBackendUrl = (import.meta.env.VITE_PUBLIC_BACKEND_URL || apiBaseUrl).replace(/\/api\/?$/, "");
const webhookCallbackUrl = `${publicBackendUrl.replace(/\/$/, "")}/api/whatsapp/webhook/`;

const setupSteps = [
  ["Create a Meta App", "Create or open a Meta developer app in the Meta Developers console."],
  ["Add WhatsApp Product", "Add the WhatsApp product and connect your business account."],
  ["Get API Credentials", "Copy the Phone Number ID, Business Account ID, and permanent access token."],
  ["Configure Webhooks", "Paste the callback URL and verify token, then subscribe to messages."],
];

function WhatsAppSettings({ embedded = false }) {
  const navigate = useNavigate();

  // WhatsApp configuration form state mirrors the backend config payload.
  const [formData, setFormData] = useState(emptyConfig);
  const [savedConfig, setSavedConfig] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [openStep, setOpenStep] = useState(0);

  useEffect(() => {
    let isMounted = true;

    // Load the saved WhatsApp config without changing existing credentials.
    getWhatsAppConfig()
      .then((config) => {
        if (!isMounted) return;
        setSavedConfig(config);
        setFormData({
          business_name: config.business_name || "",
          phone_number: config.phone_number || "",
          phone_number_id: config.phone_number_id || "",
          whatsapp_business_account_id: config.whatsapp_business_account_id || "",
          meta_app_id: config.meta_app_id || "",
          meta_app_secret: "",
          access_token: "",
          webhook_verify_token: "",
          is_active: config.is_active,
        });
      })
      .catch((requestError) => {
        if (requestError.response?.status === 401) {
          clearTokens();
          navigate("/login", { replace: true });
          return;
        }
        if (requestError.response?.status !== 404) {
          setError("Unable to load WhatsApp settings.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  function updateField(event) {
    const { name, type, checked, value } = event.target;
    setFormData((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  function buildPayload() {
    const payload = { ...formData };

    if (savedConfig) {
      ["meta_app_secret", "access_token", "webhook_verify_token"].forEach((field) => {
        if (!payload[field]) {
          delete payload[field];
        }
      });
    }

    return payload;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsSaving(true);

    try {
      const payload = buildPayload();
      const config = savedConfig
        ? await updateWhatsAppConfig(payload)
        : await createWhatsAppConfig(payload);

      setSavedConfig(config);
      setFormData({
        business_name: config.business_name || "",
        phone_number: config.phone_number || "",
        phone_number_id: config.phone_number_id || "",
        whatsapp_business_account_id: config.whatsapp_business_account_id || "",
        meta_app_id: config.meta_app_id || "",
        meta_app_secret: "",
        access_token: "",
        webhook_verify_token: "",
        is_active: config.is_active,
      });
      setMessage("WhatsApp settings saved.");
    } catch (requestError) {
      const data = requestError.response?.data;
      setError(
        data?.detail ||
          data?.phone_number_id?.[0] ||
          data?.whatsapp_business_account_id?.[0] ||
          data?.access_token?.[0] ||
          data?.webhook_verify_token?.[0] ||
          "Unable to save WhatsApp settings.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function testConnection() {
    setError("");
    setMessage("");
    if (!savedConfig) {
      setError("Save the configuration before testing Meta connectivity.");
      return;
    }
    setIsTesting(true);
    try {
      const result = await testWhatsAppConnection();
      const metadata = [result.data?.verified_name, result.data?.display_phone_number].filter(Boolean).join(" · ");
      setMessage(metadata ? `${result.message} ${metadata}` : result.message);
    } catch (requestError) {
      setError(requestError.response?.data?.message || "Unable to test the WhatsApp API connection.");
    } finally {
      setIsTesting(false);
    }
  }

  return (
    <section className={embedded ? "settings-embedded-page" : "dashboard-page"}>
      {!embedded ? (
      <div className="dashboard-header">
        <div>
          <h1>Settings</h1>
          <p>Manage your WhatsApp integration credentials and webhook setup.</p>
        </div>
        <Link className="button" to="/dashboard">
          Dashboard
        </Link>
      </div>
      ) : null}

      {!embedded ? (
        <div className="settings-tabs">
          <Link className="settings-tab" to="/settings?tab=profile">Profile</Link>
          <Link className="settings-tab settings-tab--active" to="/settings?tab=whatsapp">WhatsApp Config</Link>
          <Link className="settings-tab" to="/settings?tab=templates">Templates</Link>
          <Link className="settings-tab" to="/settings?tab=tags">Tags</Link>
          <Link className="settings-tab" to="/settings?tab=team">Team</Link>
        </div>
      ) : null}

      <SettingsSection>
      <SettingsGrid className="settings-grid--sidebar whatsapp-settings-layout">
        <SettingsCard as="form" className="settings-form whatsapp-form settings-card--primary" onSubmit={handleSubmit}>
          <div className="connection-banner">
            <span className={savedConfig?.is_active ? "status-dot status-dot--connected" : "status-dot"} />
            <div>
              <strong>{savedConfig?.is_active ? "Configuration Active" : "Configuration Inactive"}</strong>
              <p>
                {savedConfig?.is_active
                  ? "Your WhatsApp Business configuration is active."
                  : "Configure your Meta API credentials to connect your WhatsApp Business account."}
              </p>
            </div>
          </div>

          <div className="settings-card__header"><div><h2>WhatsApp configuration</h2><p>Business details, Meta identifiers, and protected API credentials.</p></div></div>
          {isLoading ? <p>Loading WhatsApp settings...</p> : null}
          {!isLoading && savedConfig ? (
            <div className="config-status">
              <span>Access Token: {savedConfig.access_token_masked || "Not set"}</span>
              <span>Webhook Verify Token: {savedConfig.webhook_verify_token_masked || "Not set"}</span>
            </div>
          ) : null}

          <div className="form-grid">
            <label>
              Business Name
              <input name="business_name" onChange={updateField} type="text" value={formData.business_name} />
            </label>
            <label>
              Phone Number
              <input name="phone_number" onChange={updateField} type="text" value={formData.phone_number} />
            </label>
            <label>
              Phone Number ID
              <input name="phone_number_id" onChange={updateField} required type="text" value={formData.phone_number_id} />
            </label>
            <label>
              WhatsApp Business Account ID
              <input
                name="whatsapp_business_account_id"
                onChange={updateField}
                required
                type="text"
                value={formData.whatsapp_business_account_id}
              />
            </label>
            <label>
              Meta App ID
              <input name="meta_app_id" onChange={updateField} type="text" value={formData.meta_app_id} />
            </label>
            <label>
              Meta App Secret
              <input
                name="meta_app_secret"
                onChange={updateField}
                placeholder={savedConfig ? "Leave blank to keep saved value" : ""}
                type="password"
                value={formData.meta_app_secret}
              />
            </label>
            <label>
              Permanent Access Token
              <input
                name="access_token"
                onChange={updateField}
                placeholder={savedConfig ? "Leave blank to keep saved value" : ""}
                required={!savedConfig}
                type="password"
                value={formData.access_token}
              />
            </label>
            <label>
              Webhook Verify Token
              <input
                name="webhook_verify_token"
                onChange={updateField}
                placeholder={savedConfig ? "Leave blank to keep saved value" : ""}
                required={!savedConfig}
                type="password"
                value={formData.webhook_verify_token}
              />
            </label>
            <label className="full-span">
              Webhook Callback URL
              <input readOnly type="text" value={webhookCallbackUrl} />
            </label>
          </div>

          <label className="checkbox-label">
            <input checked={formData.is_active} name="is_active" onChange={updateField} type="checkbox" />
            Is Active
          </label>

          {message ? <p className="form-success">{message}</p> : null}
          {error ? <p className="form-error">{error}</p> : null}

          <div className="actions">
            <button className="button button--primary" disabled={isSaving || isLoading} type="submit">
              {isSaving ? "Saving..." : "Save Configuration"}
            </button>
            <button className="button" disabled={isLoading || isTesting} onClick={testConnection} type="button">
              {isTesting ? "Testing..." : "Test API Connection"}
            </button>
          </div>
        </SettingsCard>

        <SettingsCard as="aside" className="setup-card">
          <h2>Setup Instructions</h2>
          <p>Follow these steps to connect your WhatsApp Business API.</p>
          <div className="accordion-list">
            {setupSteps.map(([title, body], index) => (
              <div className="accordion-item" key={title}>
                <button onClick={() => setOpenStep(openStep === index ? -1 : index)} type="button">
                  <span>{index + 1}</span>
                  {title}
                </button>
                {openStep === index ? <p>{body}</p> : null}
              </div>
            ))}
          </div>
          <a
            className="docs-link"
            href="https://developers.facebook.com/docs/whatsapp/cloud-api/"
            rel="noreferrer"
            target="_blank"
          >
            Meta WhatsApp API Documentation
          </a>
        </SettingsCard>
      </SettingsGrid>
      </SettingsSection>
    </section>
  );
}

export default WhatsAppSettings;
