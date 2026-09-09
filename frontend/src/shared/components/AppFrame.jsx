import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3, Bell, Building2, CircleHelp, GitBranch, KanbanSquare, LayoutDashboard, Mail,
  LogOut, Megaphone, Menu, MessageCircle, MessageSquare, Plus, Search, Settings,
  UserRound, UserRoundSearch, Users, Workflow, X,
} from "lucide-react";

import { getCurrentUser, logout } from "../services/authService.js";
import { getCurrentOrganization } from "../services/organizationService.js";
import { clearTokens } from "../services/tokenStorage.js";
import { useNotifications } from "./NotificationProvider.jsx";
import ToastStack from "./ToastStack.jsx";

const primaryLinks = [
  { label: "Dashboard", to: "/dashboard", roles: ["owner", "admin", "agent"], icon: LayoutDashboard },
  { label: "Inbox", to: "/inbox", roles: ["owner", "admin", "agent"], icon: MessageSquare },
  { label: "Contacts", to: "/contacts", roles: ["owner", "admin", "agent"], icon: Users },
  { label: "Leads", to: "/leads", roles: ["owner", "admin", "agent"], icon: UserRoundSearch },
  { label: "Lead Collector", to: "/lead-collector", roles: ["owner", "admin", "agent"], icon: Building2 },
  { label: "Email", to: "/email", roles: ["owner", "admin", "agent"], icon: Mail },
  { label: "Pipelines", to: "/pipelines", roles: ["owner", "admin", "agent"], icon: KanbanSquare },
  { label: "Broadcasts", to: "/broadcasts", roles: ["owner", "admin"], icon: Megaphone },
  { label: "Automations", to: "/automations", roles: ["owner", "admin"], icon: Workflow },
  { label: "Flows", to: "/flows", roles: ["owner", "admin"], icon: GitBranch, badge: "BETA" },
  { label: "Analytics", to: "/reports", roles: ["owner", "admin", "agent"], icon: BarChart3 },
  { label: "Settings", to: "/settings?tab=whatsapp", roles: ["owner", "admin"], icon: Settings },
];

const pageTitles = { dashboard: "Dashboard", inbox: "Inbox", contacts: "Contacts", leads: "Leads", "lead-collector": "Lead Collector", email: "Email", pipelines: "Pipelines", broadcasts: "Broadcasts", automations: "Automations", flows: "Flows", reports: "Analytics", settings: "Settings" };

function displayName(user) {
  return user?.name || user?.full_name || user?.email?.split("@")[0] || "User";
}

function AppFrame() {
  const navigate = useNavigate();
  const location = useLocation();
  const { notifications, clearNotifications } = useNotifications();
  const profileRef = useRef(null);
  const sidebarRef = useRef(null);
  const menuButtonRef = useRef(null);
  const [organization, setOrganization] = useState(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("agent");
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => window.innerWidth > 1180);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    Promise.all([getCurrentOrganization(), getCurrentUser()]).then(([org, currentUser]) => {
      if (!mounted) return;
      setOrganization(org); setRole(org.current_user_role || "agent"); setUser(currentUser);
    }).catch((error) => {
      if (error.response?.status === 401) { clearTokens(); navigate("/login", { replace: true }); }
    });
    return () => { mounted = false; };
  }, [navigate]);

  useEffect(() => { if (window.innerWidth <= 1180) setIsSidebarOpen(false); }, [location.pathname]);
  useEffect(() => {
    if (window.innerWidth > 1180) return undefined;
    document.body.style.overflow = isSidebarOpen ? "hidden" : "";
    if (isSidebarOpen) sidebarRef.current?.querySelector("a, button")?.focus();
    const closeOnEscape = (event) => {
      if (event.key === "Escape" && isSidebarOpen) {
        setIsSidebarOpen(false);
        requestAnimationFrame(() => menuButtonRef.current?.focus());
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.body.style.overflow = ""; document.removeEventListener("keydown", closeOnEscape); };
  }, [isSidebarOpen]);
  useEffect(() => {
    const close = (event) => { if (!profileRef.current?.contains(event.target)) setIsProfileOpen(false); };
    document.addEventListener("pointerdown", close); return () => document.removeEventListener("pointerdown", close);
  }, []);

  const visibleLinks = useMemo(() => primaryLinks.filter(({ roles }) => roles.includes(role)), [role]);
  const name = displayName(user);
  const pageTitle = pageTitles[location.pathname.split("/")[1]] || "WhatsApp CRM";
  const isDashboard = location.pathname === "/dashboard" || location.pathname === "/";

  async function handleLogout() {
    try { await logout(); } catch { clearTokens(); } finally { navigate("/login", { replace: true }); }
  }

  return (
    <div className={isSidebarOpen ? "app-frame app-frame--sidebar-open" : "app-frame app-frame--sidebar-closed"}>
      <aside ref={sidebarRef} className={isSidebarOpen ? "app-sidebar app-sidebar--open" : "app-sidebar"}>
        <div className="crm-brand"><span className="crm-brand__mark"><MessageCircle aria-hidden="true" size={21} /></span><span><strong>WhatsApp CRM</strong><small>Customer workspace</small></span></div>
        <nav className="app-nav" aria-label="Primary navigation">
          {visibleLinks.map(({ label, to, icon: Icon, badge }) => (
            <NavLink key={to} to={to} onClick={() => window.innerWidth <= 1180 && setIsSidebarOpen(false)} className={({ isActive }) => isActive || (label === "Settings" && location.pathname.startsWith("/settings")) ? "app-nav__link app-nav__link--active" : "app-nav__link"}>
              <span><span className="app-nav__icon" aria-hidden="true"><Icon size={17} /></span>{label}</span>{badge && <small className="nav-badge">{badge}</small>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-user"><span className="crm-avatar"><UserRound aria-hidden="true" size={18} /></span><span><strong>{name}</strong><small>{role}</small></span><button aria-label="Sign out" type="button" onClick={handleLogout}><LogOut size={16} /></button></div>
      </aside>
      {isSidebarOpen && <button className="sidebar-scrim" aria-label="Close menu" onClick={() => { setIsSidebarOpen(false); requestAnimationFrame(() => menuButtonRef.current?.focus()); }} type="button" />}
      <div className="app-main">
        <header className={isDashboard ? "topbar" : "topbar topbar--search-first"}>
          <div className="topbar-start"><button ref={menuButtonRef} className="topbar-icon menu-button" aria-label={isSidebarOpen ? "Close menu" : "Open menu"} aria-expanded={isSidebarOpen} onClick={() => setIsSidebarOpen((value) => !value)} type="button">{isSidebarOpen ? <X size={19} /> : <Menu size={19} />}</button>{isDashboard ? <strong>{pageTitle}</strong> : null}</div>
          <label className="global-search"><Search size={15} /><input aria-label="Global search" placeholder="Search customers, chats, deals..." onKeyDown={(event) => { if (event.key === "Enter") navigate("/contacts"); }} /></label>
          <div className="topbar-actions">
            <button className="topbar-new" onClick={() => navigate("/contacts")} type="button"><Plus size={16} /> <span>New</span></button>
            <button className="topbar-icon" aria-label={`Notifications (${notifications.length})`} onClick={() => setIsNotificationOpen((value) => !value)} type="button"><Bell size={17} />{notifications.length > 0 && <i />}</button>
            <button className="topbar-icon topbar-help" aria-label="Help" onClick={() => navigate("/settings")} type="button"><CircleHelp size={17} /></button>
            <div className="profile-menu" ref={profileRef}><button className="crm-avatar crm-avatar--light" aria-label="Open profile menu" onClick={() => setIsProfileOpen((value) => !value)} type="button"><UserRound aria-hidden="true" size={18} /></button>{isProfileOpen && <div className="profile-popover"><strong>{name}</strong><small>{user?.email}</small><span>{organization?.name} · {role}</span><button type="button" onClick={handleLogout}><LogOut size={15} /> Log out</button></div>}</div>
          </div>
        </header>
        {isNotificationOpen && <section className="notification-center"><div className="notification-center__header"><h2>Notifications</h2><button className="button button--small" onClick={clearNotifications} type="button">Clear</button></div>{notifications.length === 0 && <p className="empty-copy">No local notifications yet.</p>}<div className="notification-list">{notifications.map((item) => <article className={`notification-item notification-item--${item.type}`} key={item.id}><strong>{item.title}</strong>{item.message && <p>{item.message}</p>}<span>{new Date(item.createdAt).toLocaleTimeString()}</span></article>)}</div></section>}
        <Outlet context={{ role, organization, user }} />
      </div>
      <ToastStack />
    </div>
  );
}

export default AppFrame;
