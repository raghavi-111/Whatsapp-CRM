import { Link, useSearchParams } from "react-router-dom";

import OrganizationSettings from "../../whatsapp-crm/components/settings/OrganizationSettings.jsx";
import TagsSettings from "../../whatsapp-crm/components/settings/TagsSettings.jsx";
import TeamSettings from "../../whatsapp-crm/components/settings/TeamSettings.jsx";
import Templates from "../../whatsapp-crm/components/settings/Templates.jsx";
import WhatsAppSettings from "../../whatsapp-crm/components/settings/WhatsAppSettings.jsx";
import LeadCollectorSettings from "../../lead-collection/components/LeadCollectorSettings.jsx";
import "../components/settings/settings-layout.css";

/**
 * Settings Page
 *
 * Route-level configuration shell for organization settings.
 * Query-string tabs keep Profile, WhatsApp Config, Templates, Tags,
 * and Team management in one stable Settings layout.
 */

const tabs = [
  ["profile", "Profile"],
  ["whatsapp", "WhatsApp Config"],
  ["lead-collector", "Lead Collector"],
  ["templates", "Templates"],
  ["tags", "Tags"],
  ["team", "Team"],
];

const validTabs = new Set(tabs.map(([value]) => value));

function Settings() {
  const [searchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab") || "whatsapp";
  const activeTab = validTabs.has(requestedTab) ? requestedTab : "whatsapp";

  // Settings tabs are feature panels, not standalone route pages.
  function renderContent() {
    if (activeTab === "profile") return <OrganizationSettings embedded />;
    if (activeTab === "templates") return <Templates embedded />;
    if (activeTab === "tags") return <TagsSettings embedded />;
    if (activeTab === "team") return <TeamSettings embedded />;
    if (activeTab === "lead-collector") return <LeadCollectorSettings />;
    return <WhatsAppSettings embedded />;
  }

  return (
    <section className="dashboard-page settings-page">
      <div className="settings-shell">
        <div className="dashboard-header settings-header">
          <div>
            <h1>Settings</h1>
            <p>Manage workspace profile, WhatsApp configuration, Lead Collector providers, templates, tags, and team access.</p>
          </div>
          <Link className="button" to="/dashboard">
            Dashboard
          </Link>
        </div>

        <nav aria-label="Settings sections" className="settings-tabs">
          {tabs.map(([tab, label]) => (
            <Link
              className={activeTab === tab ? "settings-tab settings-tab--active" : "settings-tab"}
              key={tab}
              to={`/settings?tab=${tab}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="settings-content">{renderContent()}</div>
      </div>
    </section>
  );
}

export default Settings;
