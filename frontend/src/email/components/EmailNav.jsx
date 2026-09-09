import { NavLink } from "react-router-dom";
export default function EmailNav() {
  return <nav className="email-tabs" aria-label="Email navigation">
    <NavLink end to="/email">Overview</NavLink><NavLink to="/email/campaigns">Campaigns</NavLink><NavLink to="/email/templates">Templates</NavLink><NavLink to="/email/settings">Settings</NavLink>
  </nav>;
}
