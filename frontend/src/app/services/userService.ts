import apiClient from '@app/api/apiClient';

export interface CurrentUser {
  id: number;
  email: string;
  username: string | null;
  full_name: string | null;
  active: boolean;
  admin: boolean;
  created_at: string;
  last_login: string;
}

export interface HealthCheckResponse {
  status: string;
  database: string;
  environment?: string;
}

export const userService = {
  async getCurrentUser(): Promise<CurrentUser> {
    const response = await apiClient.get<CurrentUser>('/v1/users/me');
    return response.data;
  },

  async getHealthCheck(): Promise<HealthCheckResponse> {
    const response = await apiClient.get<HealthCheckResponse>('/v1/utils/health-check');
    return response.data;
  },

  logout(): void {
    // For OAuth2 proxy, redirect to the sign-out endpoint
    window.location.href = '/oauth2/sign_out';
  },
};
