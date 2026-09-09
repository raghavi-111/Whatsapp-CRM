const CAMPAIGNS_KEY = "crm-email-campaigns-v1";
const TEMPLATES_KEY = "crm-email-templates-v1";

const initialCampaigns = [
  { id: "c-1", name: "Delhi Hotel Outreach", recipients: 126, subject: "Partnership opportunity for your hotel", created: "Aug 16, 2026", schedule: "Aug 20, 10:30 AM", sent: 0, failed: 0, status: "Scheduled" },
  { id: "c-2", name: "Restaurant Welcome", recipients: 84, subject: "Make every guest stay connected", created: "Aug 12, 2026", schedule: "Sent Aug 13", sent: 81, failed: 3, status: "Completed" },
  { id: "c-3", name: "Q3 Business Introduction", recipients: 42, subject: "A better Wi-Fi experience", created: "Aug 17, 2026", schedule: "Not scheduled", sent: 0, failed: 0, status: "Draft" },
  { id: "c-4", name: "June Re-engagement", recipients: 58, subject: "Can we reconnect?", created: "Jun 24, 2026", schedule: "Sent Jun 25", sent: 45, failed: 13, status: "Failed" },
  { id: "c-5", name: "Hospitality Product Update", recipients: 203, subject: "What is new at TheWiFy", created: "Jul 30, 2026", schedule: "Sent Jul 31", sent: 198, failed: 5, status: "Completed" },
  { id: "c-6", name: "Mumbai Leads Follow-up", recipients: 71, subject: "Following up with {{company}}", created: "Aug 18, 2026", schedule: "Not scheduled", sent: 0, failed: 0, status: "Draft" },
];

const initialTemplates = [
  { id: "t-1", name: "Business Introduction", subject: "Partnership Opportunity for {{company}}", body: "Hello {{name}},\n\nWe would like to introduce our services and explore how we can help {{company}} deliver a better guest experience.\n\nRegards,\nTheWiFy Team", updated: "Aug 15, 2026" },
  { id: "t-2", name: "Friendly Follow-up", subject: "Following up with {{company}}", body: "Hi {{name}},\n\nI wanted to follow up on our recent conversation. Would you have time for a quick call this week?\n\nBest,\nTheWiFy Sales Team", updated: "Aug 10, 2026" },
  { id: "t-3", name: "Product Update", subject: "What is new at TheWiFy", body: "Hello {{name}},\n\nWe have launched new tools designed for businesses like {{company}}. Reply to this email if you would like a short walkthrough.\n\nRegards,\nTheWiFy Team", updated: "Jul 28, 2026" },
];

const recipients = [
  { id: "r-1", name: "Rahul Sharma", company: "Grand Hotel", email: "rahul@example.com", source: "Lead Collection" },
  { id: "r-2", name: "Priya Mehta", company: "Blue Orchid Inn", email: "priya@example.com", source: "Contacts" },
  { id: "r-3", name: "Arjun Kapoor", company: "Urban Stay", email: "arjun@urbanstay.in", source: "Lead Collection" },
  { id: "r-4", name: "Neha Verma", company: "Cafe Willow", email: "", source: "Contacts" },
  { id: "r-5", name: "Vikram Singh", company: "Palm Residency", email: "vikram-at-example.com", source: "Lead Collection" },
  { id: "r-6", name: "Ananya Rao", company: "The Fern House", email: "ananya@fernhouse.in", source: "Contacts" },
  { id: "r-7", name: "Kabir Malhotra", company: "Metro Suites", email: "kabir@metrosuites.com", source: "Lead Collection" },
  { id: "r-8", name: "Isha Patel", company: "River View Resort", email: "isha@example.com", source: "Contacts" },
];

const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { return fallback; } };
const write = (key, value) => { localStorage.setItem(key, JSON.stringify(value)); return value; };
export const getCampaigns = () => read(CAMPAIGNS_KEY, initialCampaigns);
export const getRecipients = () => recipients;
export const getTemplates = () => read(TEMPLATES_KEY, initialTemplates);
export const saveCampaign = (campaign) => write(CAMPAIGNS_KEY, [{ ...campaign, id: `c-${Date.now()}`, created: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), sent: 0, failed: 0, status: "Draft" }, ...getCampaigns()]);
export const saveTemplates = (templates) => write(TEMPLATES_KEY, templates);
export const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email || "");
