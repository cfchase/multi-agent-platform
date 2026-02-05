import apiClient from '@app/api/apiClient';

export interface Integration {
  id: number;
  service_name: string;
  expires_at: string | null;
  scopes: string | null;
  is_connected: boolean;
  is_expired: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntegrationsListResponse {
  integrations: Integration[];
  count: number;
}

export interface IntegrationStatusResponse {
  connected_services: string[];
  expired_services: string[];
  missing_services: string[];
}

export interface SupportedServicesResponse {
  services: string[];
}

export interface OAuthStartResponse {
  authorization_url: string;
  service: string;
}

export const integrationService = {
  /**
   * Get list of user's integrations
   */
  async getIntegrations(): Promise<IntegrationsListResponse> {
    const response = await apiClient.get<IntegrationsListResponse>('/v1/integrations/');
    return response.data;
  },

  /**
   * Get integration status (connected vs missing services)
   */
  async getStatus(): Promise<IntegrationStatusResponse> {
    const response = await apiClient.get<IntegrationStatusResponse>('/v1/integrations/status');
    return response.data;
  },

  /**
   * Get list of supported OAuth services
   */
  async getSupportedServices(): Promise<SupportedServicesResponse> {
    const response = await apiClient.get<SupportedServicesResponse>('/v1/integrations/services');
    return response.data;
  },

  /**
   * Start OAuth flow for a service
   * Returns the authorization URL to redirect the user to
   */
  async startOAuth(serviceName: string): Promise<OAuthStartResponse> {
    const response = await apiClient.post<OAuthStartResponse>(
      `/v1/integrations/oauth/start/${serviceName}`
    );
    return response.data;
  },

  /**
   * Disconnect an integration
   */
  async disconnect(serviceName: string): Promise<void> {
    await apiClient.delete(`/v1/integrations/${serviceName}`);
  },

  /**
   * Get display name for a service
   */
  getServiceDisplayName(serviceName: string): string {
    const displayNames: Record<string, string> = {
      google_drive: 'Google Drive',
      dataverse: 'Dataverse',
    };
    return displayNames[serviceName] || serviceName;
  },

  /**
   * Get description for a service
   */
  getServiceDescription(serviceName: string): string {
    const descriptions: Record<string, string> = {
      google_drive: 'Access files and documents from your Google Drive',
      dataverse: 'Search and retrieve data from Dataverse repositories',
    };
    return descriptions[serviceName] || 'External service integration';
  },
};
