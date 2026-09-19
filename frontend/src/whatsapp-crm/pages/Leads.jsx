import { useEffect, useState } from "react";
import { Eye, Pencil, Plus, Search, Settings2, Trash2, X } from "lucide-react";

import { getCurrentOrganization } from "../../shared/services/organizationService.js";
import {
  convertLead, createLead, createService, deleteLead, getLeadAssignees, getLeads,
  getServices, updateLead, updateService,
} from "../services/leadService.js";

const sources = ["whatsapp", "website", "blog", "instagram", "facebook", "linkedin", "qr_code", "marketing_team", "referral", "excel_import", "manual_entry", "other"];
const statuses = ["new", "contacted", "interested", "converted", "lost"];
const emptyLead = { name: "", phone: "", email: "", service: "", source: "manual_entry", status: "new", assigned_to: "", next_follow_up: "", notes: "" };
const emptyService = { name: "", code: "", description: "", is_active: true };
const label = (value) => ({ qr_code: "QR Code", marketing_team: "Marketing Team", excel_import: "Excel Import", manual_entry: "Manual Entry", whatsapp: "WhatsApp", linkedin: "LinkedIn" }[value] || value?.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "-");
const date = (value) => value ? new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "-";

function errorText(error, fallback) {
  const data = error.response?.data;
  if (data?.detail) return data.detail;
  if (data && typeof data === "object") {
    const value = Object.values(data).flat()[0];
    if (value) return String(value);
  }
  return fallback;
}

export default function Leads() {
  const [leads, setLeads] = useState([]), [services, setServices] = useState([]), [assignees, setAssignees] = useState([]);
  const [role, setRole] = useState("agent"), [filters, setFilters] = useState({ search: "", service: "", source: "", status: "", assigned_to: "", page: 1 });
  const [total, setTotal] = useState(0), [loading, setLoading] = useState(true), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [summary, setSummary] = useState({ new: 0, inProgress: 0, qualified: 0, converted: 0 });
  const [form, setForm] = useState(null), [selected, setSelected] = useState(null), [servicesOpen, setServicesOpen] = useState(false), [serviceForm, setServiceForm] = useState(null), [saving, setSaving] = useState(false);
  const canManage = role === "owner" || role === "admin";

  useEffect(() => { Promise.all([getServices(), getLeadAssignees(), getCurrentOrganization()]).then(([s, a, o]) => { setServices(s); setAssignees(a); setRole(o.current_user_role || "agent"); }).catch((e) => setError(errorText(e, "Unable to load lead options."))); }, []);
  useEffect(() => { Promise.all(["new", "contacted", "interested", "converted"].map((status) => getLeads({ status, page: 1 }))).then(([newLeads, contacted, interested, converted]) => setSummary({ new: newLeads.count, inProgress: contacted.count, qualified: interested.count, converted: converted.count })).catch(() => {}); }, [message]);
  useEffect(() => { const timer = setTimeout(loadLeads, 250); return () => clearTimeout(timer); }, [filters]);

  async function loadLeads() {
    setLoading(true); setError("");
    try { const data = await getLeads(filters); setLeads(data.results); setTotal(data.count); }
    catch (e) { setError(errorText(e, "Unable to load leads.")); }
    finally { setLoading(false); }
  }
  function changeFilter(e) { setFilters((v) => ({ ...v, [e.target.name]: e.target.value, page: 1 })); }
  function edit(lead = null) {
    setSelected(lead); setForm(lead ? { ...lead, service: String(lead.service), assigned_to: lead.assigned_to || "", next_follow_up: lead.next_follow_up?.slice(0, 16) || "" } : { ...emptyLead }); setError("");
  }
  async function saveLead(e) {
    e.preventDefault(); setSaving(true); setError("");
    const payload = { ...form, service: Number(form.service), assigned_to: form.assigned_to ? Number(form.assigned_to) : null, next_follow_up: form.next_follow_up || null };
    try { selected ? await updateLead(selected.id, payload) : await createLead(payload); setForm(null); setSelected(null); setMessage(selected ? "Lead updated." : "Lead created."); await loadLeads(); }
    catch (err) { setError(errorText(err, "Unable to save lead.")); }
    finally { setSaving(false); }
  }
  async function remove(lead) { if (!window.confirm(`Delete ${lead.name}?`)) return; try { await deleteLead(lead.id); setMessage("Lead deleted."); await loadLeads(); } catch (e) { setError(errorText(e, "Unable to delete lead.")); } }
  async function convert(lead) { if (!window.confirm(`Convert ${lead.name} to a deal?`)) return; try { const deal = await convertLead(lead.id); setMessage(`Deal “${deal.title}” created.`); setSelected(null); await loadLeads(); } catch (e) { setError(errorText(e, "Unable to convert lead.")); } }
  async function saveService(e) {
    e.preventDefault(); setSaving(true); setError("");
    try { serviceForm.id ? await updateService(serviceForm.id, serviceForm) : await createService(serviceForm); setServiceForm(null); setServices(await getServices()); setMessage("Service saved."); }
    catch (err) { setError(errorText(err, "Unable to save service.")); }
    finally { setSaving(false); }
  }

  return <section className="dashboard-page leads-page">
    <div className="dashboard-header leads-page__header"><div><h1>Leads</h1><p>Qualify inquiries and convert genuine interest into pipeline deals.</p></div><div className="actions">
      {canManage && <button className="button" onClick={() => setServicesOpen(true)}><Settings2 size={16}/>Manage services</button>}
      <button className="button button--primary" onClick={() => edit()}><Plus size={16}/>New lead</button>
    </div></div>
    {message && <p className="form-success">{message}</p>}{error && !form && !servicesOpen && <p className="form-error">{error}</p>}
    <section className="lead-metrics">{[["New leads",summary.new,"blue"],["In progress",summary.inProgress,"orange"],["Qualified",summary.qualified,"purple"],["Converted",summary.converted,"green"]].map(([title,count,tone])=><article key={title}><i className={`lead-metric-icon lead-metric-icon--${tone}`}/><span>{title}</span><strong>{count}</strong></article>)}</section>
    <div className="panel leads-filters"><label className="leads-search"><Search size={14}/><input aria-label="Search leads" name="search" onChange={changeFilter} placeholder="Search name, phone, or email" value={filters.search}/></label>
      <select name="service" onChange={changeFilter} value={filters.service}><option value="">All services</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      <select name="source" onChange={changeFilter} value={filters.source}><option value="">All sources</option>{sources.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select name="status" onChange={changeFilter} value={filters.status}><option value="">All statuses</option>{statuses.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select name="assigned_to" onChange={changeFilter} value={filters.assigned_to}><option value="">All assignees</option>{assignees.map((a) => <option key={a.id} value={a.id}>{a.email}</option>)}</select>
      <button aria-label="Clear filters" className="leads-clear" onClick={() => setFilters({ search: "", service: "", source: "", status: "", assigned_to: "", page: 1 })}><X size={14}/></button>
    </div>
    {loading ? <p className="dashboard-loading">Loading leads...</p> : leads.length === 0 ? <div className="empty-state"><strong>{Object.values(filters).some((v) => v && v !== 1) ? "No matching leads" : "No leads yet"}</strong><span>{Object.values(filters).some((v) => v && v !== 1) ? "Clear filters or try another search." : "Create the first lead to start qualifying inquiries."}</span></div> : <div className="panel table-wrap leads-table-panel"><table className="data-table leads-table"><thead><tr>{["Lead","Phone","Service","Source","Status","Assigned","Follow-up","Created",""].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{leads.map((lead) => <tr key={lead.id} onClick={() => setSelected(lead)}><td><strong>{lead.name}</strong><small>{lead.email || ""}</small></td><td>{lead.phone}</td><td>{lead.service_name}</td><td>{label(lead.source)}</td><td><span className={`pill pill--${lead.status}`}>{label(lead.status)}</span></td><td>{lead.assigned_to_email || "Unassigned"}</td><td>{date(lead.next_follow_up)}</td><td>{date(lead.created_at)}</td><td><button className="lead-open-button" aria-label="Open lead" onClick={(e) => { e.stopPropagation(); setSelected(lead); }}><Eye size={14}/></button></td></tr>)}</tbody></table></div>}
    {total > 20 && <div className="table-pagination"><span>Page {filters.page} of {Math.ceil(total / 20)}</span><div className="actions"><button className="button" disabled={filters.page <= 1} onClick={() => setFilters((v) => ({...v,page:v.page-1}))}>Previous</button><button className="button" disabled={filters.page >= Math.ceil(total/20)} onClick={() => setFilters((v) => ({...v,page:v.page+1}))}>Next</button></div></div>}

    {selected && !form && <div className="deal-modal"><div className="contact-modal__scrim" onClick={() => setSelected(null)}/><div className="panel deal-detail-modal" role="dialog" aria-modal="true"><div className="contact-form__header"><h2>{selected.name}</h2><button className="icon-button" onClick={() => setSelected(null)}><X size={16}/></button></div><dl className="deal-detail-list">{[["Phone",selected.phone],["Email",selected.email||"-"],["Service",selected.service_name],["Source",label(selected.source)],["Status",label(selected.status)],["Assigned employee",selected.assigned_to_email||"Unassigned"],["Next follow-up",date(selected.next_follow_up)],["Created",date(selected.created_at)],["Updated",date(selected.updated_at)],["Converted deal",selected.converted_deal_details?.title||"-"]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl><p className="lead-notes">{selected.notes || "No notes."}</p><div className="actions"><button className="button" onClick={() => edit(selected)}><Pencil size={16}/>Edit</button><button className="button button--primary" disabled={selected.status !== "interested"} onClick={() => convert(selected)}>Convert to Deal</button>{selected.converted_deal && <a className="button" href="/pipelines">Open Deal</a>}</div></div></div>}
    {form && <div className="deal-modal"><div className="contact-modal__scrim" onClick={() => setForm(null)}/><form className="panel deal-detail-modal" onSubmit={saveLead}><div className="contact-form__header"><h2>{selected ? "Edit lead" : "New lead"}</h2><button className="icon-button" type="button" onClick={() => setForm(null)}><X size={16}/></button></div><div className="form-grid">
      <label>Lead name<input required value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})}/></label><label>Phone<input required type="tel" value={form.phone} onChange={(e)=>setForm({...form,phone:e.target.value})}/></label><label>Email<input type="email" value={form.email} onChange={(e)=>setForm({...form,email:e.target.value})}/></label><label>Service<select required value={form.service} onChange={(e)=>setForm({...form,service:e.target.value})}><option value="">Select service</option>{services.filter((s)=>s.is_active || s.id===selected?.service).map((s)=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Source<select required value={form.source} onChange={(e)=>setForm({...form,source:e.target.value})}>{sources.map((s)=><option key={s} value={s}>{label(s)}</option>)}</select></label><label>Status<select required value={form.status} onChange={(e)=>setForm({...form,status:e.target.value})}>{statuses.filter((s)=>s!=="converted" || selected?.converted_deal).map((s)=><option key={s} value={s}>{label(s)}</option>)}</select></label><label>Assigned To<select value={form.assigned_to} onChange={(e)=>setForm({...form,assigned_to:e.target.value})}><option value="">Unassigned</option>{assignees.map((a)=><option key={a.id} value={a.id}>{a.email}</option>)}</select></label><label>Next follow-up<input type="datetime-local" value={form.next_follow_up} onChange={(e)=>setForm({...form,next_follow_up:e.target.value})}/></label></div><label>Notes<textarea rows="4" value={form.notes} onChange={(e)=>setForm({...form,notes:e.target.value})}/></label>{error&&<p className="form-error">{error}</p>}<div className="actions"><button className="button button--primary" disabled={saving}>{saving?"Saving...":"Save Lead"}</button><button className="button" type="button" onClick={()=>setForm(null)}>Cancel</button></div></form></div>}
    {servicesOpen && <div className="deal-modal"><div className="contact-modal__scrim" onClick={()=>setServicesOpen(false)}/><div className="panel deal-detail-modal"><div className="contact-form__header"><h2>Services</h2><button className="icon-button" onClick={()=>setServicesOpen(false)}><X size={16}/></button></div><button className="button button--primary" onClick={()=>setServiceForm({...emptyService})}><Plus size={16}/>New Service</button><div className="service-list">{services.map((s)=><div className="service-row" key={s.id}><div><strong>{s.name}</strong><small>{s.code} · {s.is_active?"Active":"Inactive"}</small></div><div className="actions"><button className="button" onClick={()=>setServiceForm({...s})}>Edit</button><button className="button" onClick={async()=>{await updateService(s.id,{is_active:!s.is_active});setServices(await getServices());}}>{s.is_active?"Deactivate":"Activate"}</button></div></div>)}</div>{serviceForm&&<form className="service-form" onSubmit={saveService}><div className="form-grid"><label>Name<input required value={serviceForm.name} onChange={(e)=>setServiceForm({...serviceForm,name:e.target.value})}/></label><label>Code<input required value={serviceForm.code} onChange={(e)=>setServiceForm({...serviceForm,code:e.target.value})}/></label></div><label>Description<textarea rows="3" value={serviceForm.description} onChange={(e)=>setServiceForm({...serviceForm,description:e.target.value})}/></label><label className="checkbox-row"><input type="checkbox" checked={serviceForm.is_active} onChange={(e)=>setServiceForm({...serviceForm,is_active:e.target.checked})}/>Active</label>{error&&<p className="form-error">{error}</p>}<div className="actions"><button className="button button--primary" disabled={saving}>Save Service</button><button className="button" type="button" onClick={()=>setServiceForm(null)}>Cancel</button></div></form>}</div></div>}
  </section>;
}
