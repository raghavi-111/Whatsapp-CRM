import apiClient from "../../shared/services/apiClient.js";

export async function getFlows() { return (await apiClient.get("/flows/")).data; }
export async function getFlow(id) { return (await apiClient.get(`/flows/${id}/`)).data; }
export async function createFlow(data) { return (await apiClient.post("/flows/", data)).data; }
export async function updateFlow(id, data) { return (await apiClient.patch(`/flows/${id}/`, data)).data; }
export async function deleteFlow(id) { await apiClient.delete(`/flows/${id}/`); }
export async function getFlowRuns() { return (await apiClient.get("/flows/runs/")).data; }
export async function getFlowLogs(runId) { return (await apiClient.get("/flows/logs/", { params: { run: runId } })).data; }
export async function cancelFlowRun(id) { return (await apiClient.post(`/flows/runs/${id}/cancel/`)).data; }
export async function restartFlowRun(id) { return (await apiClient.post(`/flows/runs/${id}/restart/`)).data; }
export async function getMedia() { return (await apiClient.get("/media/")).data; }
export async function uploadMedia(file) {
  const data = new FormData();
  data.append("file", file);
  return (await apiClient.post("/media/upload/", data)).data;
}
