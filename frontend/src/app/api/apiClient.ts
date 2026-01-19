import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
});

// Response interceptor for handling 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // User is not authenticated, redirect to OAuth proxy
      // In local dev, OAuth runs on port 4180; in production, same origin
      const isLocalDev = window.location.port === '8080';
      const oauthUrl = isLocalDev ? 'http://localhost:4180/' : '/oauth2/start';
      window.location.href = oauthUrl;
    }
    return Promise.reject(error);
  }
);

export default apiClient;
