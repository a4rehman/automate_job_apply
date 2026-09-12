const API_BASE = '/api/v1';

function getHeaders(isJson = true) {
  const token = localStorage.getItem('token');
  const headers = {};
  if (isJson) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function request(endpoint, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = {
    ...getHeaders(!isFormData),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem('token');
    window.dispatchEvent(new Event('auth:unauthorized'));
  }

  if (!response.ok) {
    let errorDetail = 'Request failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errorDetail = response.statusText;
    }
    throw new Error(errorDetail);
  }

  // Handle empty responses (like 204)
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

export const api = {
  // Auth
  login: async (email, password) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }
    return res.json();
  },
  register: (data) => request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => request('/auth/me'),

  // Profile & Resume
  getProfile: () => request('/profile'),
  updateProfile: (data) => request('/profile', { method: 'PUT', body: JSON.stringify(data) }),
  addSkill: (data) => request('/profile/skills', { method: 'POST', body: JSON.stringify(data) }),
  deleteSkill: (id) => request(`/profile/skills/${id}`, { method: 'DELETE' }),
  uploadResume: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/profile/resume/upload', { method: 'POST', body: formData });
  },

  // Jobs
  getJobs: (params = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') searchParams.append(k, v);
    });
    return request(`/jobs?${searchParams.toString()}`);
  },
  getJob: (id) => request(`/jobs/${id}`),
  createJobManual: (data) => request('/jobs/manual', { method: 'POST', body: JSON.stringify(data) }),
  updateJobStatus: (id, status) => request(`/jobs/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  analyzeJob: (id) => request(`/jobs/${id}/analyze`, { method: 'POST' }),

  // Applications (Human-In-The-Loop)
  getApplications: (params = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') searchParams.append(k, v);
    });
    return request(`/applications?${searchParams.toString()}`);
  },
  getApplication: (id) => request(`/applications/${id}`),
  prepareApplication: (jobId, data = {}) => request(`/applications/prepare/${jobId}`, { method: 'POST', body: JSON.stringify(data) }),
  approveApplication: (id, data = {}) => request(`/applications/${id}/approve`, { method: 'POST', body: JSON.stringify(data) }),
  markApplicationSubmitted: (id, data = {}) => request(`/applications/${id}/mark-submitted`, { method: 'POST', body: JSON.stringify(data) }),
  updateApplicationStatus: (id, status) => request(`/applications/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),

  // Automation & Sources
  getAutomationSettings: () => request('/automation/settings'),
  updateAutomationSettings: (data) => request('/automation/settings', { method: 'PUT', body: JSON.stringify(data) }),
  triggerAutomationRun: () => request('/automation/run-now', { method: 'POST' }),
  getSources: () => request('/sources'),

  // Analytics & Audit
  getKPIs: () => request('/analytics/kpis'),
  getMatchDistribution: () => request('/analytics/match-distribution'),
  getFunnel: () => request('/analytics/funnel'),
  getNotifications: (params = {}) => request('/notifications'),
  markNotificationsRead: () => request('/notifications/read-all', { method: 'POST' }),
  getAuditLogs: (params = {}) => request('/audit/logs'),
};
