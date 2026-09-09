import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App.jsx";
import "./styles.css";
import "./whatsapp-crm/pages/Leads.css";
import "./whatsapp-crm/pages/LeadsOverrides.css";
import "./shared/components/AppFrameOverrides.css";
import "./email/email.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
