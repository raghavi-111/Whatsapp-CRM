import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { UserRound } from "lucide-react";
import { cancelFlowRun, deleteFlow, getFlowLogs, getFlowRuns, getFlows, restartFlowRun } from "../services/flowService.js";

const stepLabels = { send_text: "Send message", send_template: "Send template", send_media: "Send media", ask_question: "Ask question", wait_reply: "Wait for reply", options: "Options", branch: "Branch by reply", add_tag: "Add tag", remove_tag: "Remove tag", create_deal: "Create deal", update_deal: "Update deal", assign_member: "Assign member", notify_team: "Notify team", delay: "Delay", end: "End" };
const stepTones = ["blue", "blue", "orange", "purple", "green"];

function relativeTime(value) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function initials() {
  return <UserRound aria-hidden="true" size={18} />;
}

function Flows() {
  const [flows, setFlows] = useState([]);
  const [runs, setRuns] = useState([]);
  const [logs, setLogs] = useState({ runId: null, items: [] });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([getFlows(), getFlowRuns()])
      .then(([flowItems, runItems]) => { setFlows(flowItems); setRuns(runItems); })
      .catch(() => setError("Unable to load flows and runs."))
      .finally(() => setIsLoading(false));
  }, []);

  async function remove(id) { await deleteFlow(id); setFlows((items) => items.filter((item) => item.id !== id)); }
  async function cancelRun(id) { try { const updated = await cancelFlowRun(id); setRuns((items) => items.map((item) => item.id === id ? updated : item)); } catch { setError("Unable to cancel the flow run."); } }
  async function restartRun(id) { try { const result = await restartFlowRun(id); setRuns((items) => [result.run, ...items.map((item) => item.id === id ? result.previous_run : item)]); } catch { setError("Unable to restart the flow run."); } }
  async function viewLogs(id) { try { setLogs({ runId: id, items: await getFlowLogs(id) }); } catch { setError("Unable to load flow logs."); } }

  const activeRuns = runs.filter((run) => ["running", "waiting"].includes(run.status));
  const activeFlows = flows.filter((flow) => flow.status === "active");
  const today = new Date().toDateString();
  const completedToday = runs.filter((run) => run.status === "completed" && new Date(run.completed_at || run.updated_at).toDateString() === today).length;
  const failedToday = runs.filter((run) => run.status === "failed" && new Date(run.updated_at).toDateString() === today).length;
  const completedRuns = runs.filter((run) => run.status === "completed").length;
  const failedRuns = runs.filter((run) => run.status === "failed").length;
  const completionRate = runs.length ? Math.round((completedRuns / runs.length) * 100) : 0;
  const failureRate = runs.length ? Math.round((failedRuns / runs.length) * 100) : 0;
  const waitingRate = runs.length ? Math.round((runs.filter((run) => run.status === "waiting").length / runs.length) * 100) : 0;
  const featuredFlow = flows[0];
  const featuredSteps = (featuredFlow?.steps_json || []).slice(0, 5);

  return <section className="dashboard-page flows-page">
    <header className="dashboard-header flows-page__header"><div><h1>Flows</h1><p>Build stateful, multi-step customer conversation journeys.</p></div><div className="flows-header-actions"><Link className="button" to="/automations/new">Open automation builder</Link><Link className="button button--primary" to="/flows/new">Create flow</Link></div></header>
    {error ? <p className="form-error">{error}</p> : null}
    {isLoading ? <div className="flows-loading">Loading flows...</div> : <>
      <section className="flows-metrics" aria-label="Flow metrics">
        {[['Active flows', activeFlows.length], ['Waiting runs', runs.filter((run) => run.status === 'waiting').length], ['Completed today', completedToday], ['Failed today', failedToday]].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}
      </section>
      {!featuredFlow ? <div className="flows-empty"><strong>No flows created yet</strong><span>Create a flow journey, or open Automations for trigger-condition-action rules.</span><Link className="button button--primary" to="/flows/new">Create flow</Link></div> : <article className="flow-feature-card">
        <div className="flow-feature-heading"><div><h2>{featuredFlow.name}</h2><p>{featuredFlow.description || "No description"}</p></div><span className={`flow-status flow-status--${featuredFlow.status}`}>{featuredFlow.status}</span></div>
        <div className="flow-journey" aria-label={`${featuredFlow.name} journey preview`}>
          {(featuredSteps.length ? featuredSteps : [{ type: "end" }]).map((step, index, items) => <div className="flow-step-wrap" key={`${step.type}-${index}`}><div className={`flow-step flow-step--${stepTones[index % stepTones.length]}`}>{step.label || step.name || stepLabels[step.type] || step.type}</div>{index < items.length - 1 ? <i /> : null}</div>)}
          <div className="flow-card-actions"><Link className="button button--small" to={`/flows/${featuredFlow.id}/edit`}>Edit</Link><button className="button button--small" onClick={() => remove(featuredFlow.id)} type="button">Delete</button></div>
        </div>
      </article>}
      <section className="flows-bottom-grid">
        <article className="flows-panel flows-runs-panel"><h2>Active and waiting runs</h2>{!activeRuns.length ? <p className="flows-panel-empty">No active customer flow runs.</p> : <div className="flow-run-list">{activeRuns.slice(0, 4).map((run) => { const name = run.contact_name || run.contact_phone || `Contact ${run.contact}`; return <div className="flow-run-row" key={run.id}><span className="flow-run-avatar">{initials(name)}</span><span><strong>{name}</strong><small>{run.status === "waiting" ? "Waiting for reply" : `${run.flow_name} · Step ${run.current_step + 1}`}</small></span><time>{relativeTime(run.updated_at)}</time><div className="flow-run-actions"><button onClick={() => restartRun(run.id)} type="button">Restart</button><button onClick={() => cancelRun(run.id)} type="button">Cancel</button><button onClick={() => viewLogs(run.id)} type="button">Logs</button></div></div>; })}</div>}</article>
        <article className="flows-panel flow-performance"><h2>Flow performance</h2>{[['Completion rate', completionRate, 'green'], ['Waiting rate', waitingRate, 'blue'], ['Failure rate', failureRate, 'red']].map(([label, value, tone]) => <div className="flow-performance-row" key={label}><div><span>{label}</span><strong>{value}%</strong></div><div><i className={`flow-progress--${tone}`} style={{ width: `${value}%` }}/></div></div>)}</article>
      </section>
    </>}
    {logs.runId ? <section className="flows-log-panel"><div><h2>Run {logs.runId} logs</h2><button onClick={() => setLogs({ runId: null, items: [] })} type="button">Close</button></div>{logs.items.map((log) => <p key={log.id}><strong>{log.status}</strong> · Step {log.step_index + 1} · {log.step_type} — {log.message || relativeTime(log.created_at)}</p>)}</section> : null}
  </section>;
}

export default Flows;
