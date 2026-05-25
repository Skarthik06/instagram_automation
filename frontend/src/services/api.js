import axios from 'axios';

const http = axios.create({ baseURL: '/api', timeout: 0 });
const data = (r) => r.data;

export default {
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
};
