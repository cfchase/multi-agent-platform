import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
});

// Response interceptor for handling 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // User is not authenticated, redirect to OAuth login
      window.location.href = '/oauth2/sign_out';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
