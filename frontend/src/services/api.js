import axios from 'axios';

const http = axios.create({ baseURL: '/api', timeout: 0 });
const data = (r) => r.data;

export const TOKEN_KEY = 'ig_admin_token';
export const REFRESH_KEY = 'ig_admin_refresh';

// Attach the admin bearer token to every request.
http.interceptors.request.use((config) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// On 401 (expired/invalid token), drop the session so the app returns to login.
http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && !err.config?.url?.includes('/v1/admin/login')) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      if (!window.__ig_loggingOut) { window.__ig_loggingOut = true; window.location.reload(); }
    }
    return Promise.reject(err);
  }
);

export default {
  // single-admin auth
  adminLogin: (username, password) => http.post('/v1/admin/login', { username, password }).then(data),
  adminMe: () => http.get('/v1/admin/me').then(data),
  adminLogout: () => http.post('/v1/admin/logout').then(data).catch(() => {}),
  adminAudit: (limit = 100) => http.get('/v1/admin/audit', { params: { limit } }).then(data),

  // health
  health: () => http.get('/health').then(data),

  // accounts (rags)
  listAccounts: (niche) => http.get('/accounts', { params: niche ? { niche } : {} }).then(data),
  createAccount: (body) => http.post('/accounts', body).then(data),
  updateAccount: (id, body) => http.put(`/accounts/${id}`, body).then(data),
  deleteAccount: (id) => http.delete(`/accounts/${id}`).then(data),

  // settings (rags)
  getSettings: () => http.get('/settings').then(data),
  updateSettings: (body) => http.put('/settings', body).then(data),

  // generation
  generate: (body) => http.post('/generate', body).then(data),
  getBatch: (id) => http.get(`/batch/${id}`).then(data),
  publish: (body) => http.post('/publish', body).then(data),

  // news preview
  getNews: (topic) => http.get('/news', { params: topic ? { topic } : {} }).then(data),

  // history / stats
  getPosts: (limit = 50, niche) => http.get('/posts', { params: { limit, ...(niche ? { niche } : {}) } }).then(data),
  getStats: () => http.get('/stats').then(data),

  // business — real-estate document intelligence
  bizDocuments: () => http.get('/business/documents').then(data),
  bizUpload: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return http.post('/business/documents', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(data);
  },
  // Multi-file upload — any file types in one request (Agent 01 Ingestion).
  bizUploadMulti: (files) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append('files', f));
    return http.post('/business/documents/batch', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(data);
  },
  // Agent 08 — 2-3 recommended campaign batches, each a 6-9 slide carousel.
  bizRecommendBatch: (body) => http.post('/business/campaigns/recommend-batch', body).then(data),
  bizGenerate: (body) => http.post('/business/generate', body).then(data),
  bizBriefOptions: () => http.get('/business/brief/options').then(data),
  bizExtract: (document) => http.post('/business/extract', { document }).then(data),
  bizGenerateCampaign: (body) => http.post('/business/campaigns/generate', body).then(data),
  bizProperties: () => http.get('/business/properties').then(data),
  bizDashboard: () => http.get('/business/dashboard/summary').then(data),
  bizWorkspace: (pid) => http.get(`/business/properties/${pid}/workspace`).then(data),
  bizVersions: (pid) => http.get(`/business/properties/${pid}/versions`).then(data),
  bizAnalyticsOverview: () => http.get('/business/analytics/overview').then(data),
  bizMedia: (category) => http.get('/business/media', { params: category ? { category } : {} }).then(data),
  bizIntegrations: () => http.get('/business/integrations/status').then(data),
  bizGithubStatus: () => http.get('/business/github/status').then(data),
  // /api/v1 (enveloped) — leads + schedules
  v1Leads: () => http.get('/v1/leads').then((r) => r.data.data),
  v1CreateLead: (body) => http.post('/v1/leads', body).then((r) => r.data.data),
  v1LeadStatus: (id, status) => http.put(`/v1/leads/${id}/status`, { status }).then((r) => r.data.data),
  v1Schedules: () => http.get('/v1/schedules').then((r) => r.data.data),
  bizBlueprint: (cid) => http.get(`/business/campaigns/${cid}/blueprint`).then(data),
  bizEditSlide: (cid, i, body, render = true) => http.put(`/business/campaigns/${cid}/slides/${i}?render=${render}`, body).then(data),
  bizCustomGenerate: (body) => http.post('/business/custom/generate', body).then(data),
  bizCustomUpload: (files) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append('files', f));
    return http.post('/business/custom/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(data);
  },
  bizLockSlide: (cid, i) => http.post(`/business/campaigns/${cid}/slides/${i}/lock`).then(data),
  bizUnlockSlide: (cid, i) => http.post(`/business/campaigns/${cid}/slides/${i}/unlock`).then(data),
  bizRegenSlide: (cid, i, mode) => http.post(`/business/campaigns/${cid}/slides/${i}/regenerate`, { mode, render: true }).then(data),
  bizReorder: (cid, order) => http.post(`/business/campaigns/${cid}/blueprint/reorder`, { order, render: true }).then(data),
  bizRerender: (cid) => http.post(`/business/campaigns/${cid}/render`).then(data),
  bizBrands: () => http.get('/business/brands').then(data),
  bizCreateBrand: (body) => http.post('/business/brands', body).then(data),
  bizAccounts: () => http.get('/business/accounts').then(data),
  bizPublish: (cid, account_id, dry_run) => http.post(`/business/campaigns/${cid}/publish`, { account_id, dry_run }).then(data),
  bizSyncAnalytics: (cid, account_id) => http.post(`/business/campaigns/${cid}/analytics/sync`, { account_id }).then(data),
  bizCampaignAnalytics: (cid) => http.get(`/business/analytics/campaigns/${cid}`).then(data),
  bizProperty: (id) => http.get(`/business/properties/${id}`).then(data),
  bizSetStatus: (campaignId, status) => http.put(`/business/campaigns/${campaignId}/status`, { status }).then(data),
};
