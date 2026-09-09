import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "../shared/components/ProtectedRoute.jsx";
import AppFrame from "../shared/components/AppFrame.jsx";
import Automations from "../whatsapp-crm/pages/Automations.jsx";
import AutomationBuilder from "../whatsapp-crm/pages/AutomationBuilder.jsx";
import Broadcasts from "../whatsapp-crm/pages/Broadcasts.jsx";
import Contacts from "../whatsapp-crm/pages/Contacts.jsx";
import Flows from "../whatsapp-crm/pages/Flows.jsx";
import FlowBuilder from "../whatsapp-crm/pages/FlowBuilder.jsx";
import Inbox from "../whatsapp-crm/pages/Inbox.jsx";
import InviteAccept from "../shared/pages/InviteAccept.jsx";
import MainLayout from "../shared/layouts/MainLayout.jsx";
import Dashboard from "../whatsapp-crm/pages/Dashboard.jsx";
import Login from "../shared/pages/Login.jsx";
import Leads from "../whatsapp-crm/pages/Leads.jsx";
import LeadCollector from "../lead-collection/pages/LeadCollector.jsx";
import Pipelines from "../whatsapp-crm/pages/Pipelines.jsx";
import Register from "../shared/pages/Register.jsx";
import Reports from "../whatsapp-crm/pages/Reports.jsx";
import Settings from "../shared/pages/Settings.jsx";
import EmailDashboard from "../email/pages/EmailDashboard.jsx";
import EmailCampaigns from "../email/pages/EmailCampaigns.jsx";
import CreateEmailCampaign from "../email/pages/CreateEmailCampaign.jsx";
import EmailTemplates from "../email/pages/EmailTemplates.jsx";
import EmailSettings from "../email/pages/EmailSettings.jsx";

function AppRoutes() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<Navigate replace to="/login" />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="invite/accept/:token" element={<InviteAccept />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppFrame />}>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="contacts" element={<Contacts />} />
            <Route path="leads" element={<Leads />} />
            <Route path="lead-collector" element={<LeadCollector />} />
            <Route path="email" element={<EmailDashboard />} />
            <Route path="email/campaigns" element={<EmailCampaigns />} />
            <Route path="email/campaigns/new" element={<CreateEmailCampaign />} />
            <Route path="email/templates" element={<EmailTemplates />} />
            <Route path="email/settings" element={<EmailSettings />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="pipelines" element={<Pipelines />} />
            <Route path="broadcasts" element={<Broadcasts />} />
            <Route path="automations" element={<Automations />} />
            <Route path="automations/new" element={<AutomationBuilder />} />
            <Route path="flows" element={<Flows />} />
            <Route path="flows/new" element={<FlowBuilder />} />
            <Route path="flows/:flowId/edit" element={<FlowBuilder />} />
            <Route path="reports" element={<Reports />} />
            <Route path="settings" element={<Settings />} />
            <Route path="settings/organization" element={<Navigate replace to="/settings?tab=profile" />} />
            <Route path="settings/tags" element={<Navigate replace to="/settings?tab=tags" />} />
            <Route path="settings/team" element={<Navigate replace to="/settings?tab=team" />} />
            <Route path="settings/whatsapp" element={<Navigate replace to="/settings?tab=whatsapp" />} />
            <Route path="settings/lead-collector" element={<Navigate replace to="/settings?tab=lead-collector" />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}

export default AppRoutes;
