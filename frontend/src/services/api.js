import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 0, // No timeout - wait forever!
});

export default {
  getStats: () => api.get('/stats').then(r => r.data),
  getAnalytics: () => api.get('/analytics').then(r => r.data),
  generatePreviews: () => api.post('/generate-previews').then(r => r.data),
  getCurrentPreviews: () => api.get('/current-previews').then(r => r.data),
  postImage: (index) => api.post('/post-image', { image_index: index }).then(r => r.data),
  rejectPreviews: () => api.post('/reject-previews').then(r => r.data),
  getPosts: (limit = 50, offset = 0) => api.get(`/posts?limit=${limit}&offset=${offset}`).then(r => r.data),
};
