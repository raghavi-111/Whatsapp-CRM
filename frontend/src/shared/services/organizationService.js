import apiClient from "./apiClient.js";

export async function getCurrentOrganization() {
  const response = await apiClient.get("/organizations/current/");
  return response.data;
}

export async function updateCurrentOrganization({ name }) {
  const response = await apiClient.patch("/organizations/current/", { name });
  return response.data;
}

export async function getOrganizationMembers() {
  const response = await apiClient.get("/organizations/members/");
  return response.data;
}

export async function updateOrganizationMember(memberId, data) {
  const response = await apiClient.patch(`/organizations/members/${memberId}/`, data);
  return response.data;
}

export async function removeOrganizationMember(memberId) {
  await apiClient.delete(`/organizations/members/${memberId}/`);
}

export async function getOrganizationInvitations() {
  const response = await apiClient.get("/organizations/invitations/");
  return response.data;
}

export async function getOrganizationInvitation(token) {
  const response = await apiClient.get(`/organizations/invitations/${token}/`);
  return response.data;
}

export async function createOrganizationInvitation(data) {
  const response = await apiClient.post("/organizations/invitations/", data);
  return response.data;
}

export async function cancelOrganizationInvitation(invitationId) {
  const response = await apiClient.patch(`/organizations/invitations/${invitationId}/cancel/`);
  return response.data;
}

export async function acceptOrganizationInvitation(token) {
  const response = await apiClient.post(`/organizations/invitations/${token}/accept/`);
  return response.data;
}
