import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { IntegrationSettings } from './IntegrationSettings';
import { integrationService } from '@app/services/integrationService';

// Mock the integration service
vi.mock('@app/services/integrationService', () => ({
  integrationService: {
    getIntegrations: vi.fn(),
    getStatus: vi.fn(),
    getSupportedServices: vi.fn(),
    startOAuth: vi.fn(),
    disconnect: vi.fn(),
    getServiceDisplayName: vi.fn((name: string) => {
      const names: Record<string, string> = {
        google_drive: 'Google Drive',
        dataverse: 'Dataverse',
      };
      return names[name] || name;
    }),
    getServiceDescription: vi.fn(() => 'Service description'),
  },
}));

describe('IntegrationSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(integrationService.getStatus).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );
    vi.mocked(integrationService.getIntegrations).mockImplementation(
      () => new Promise(() => {})
    );
    vi.mocked(integrationService.getSupportedServices).mockImplementation(
      () => new Promise(() => {})
    );

    render(<IntegrationSettings />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders service cards when data loads', async () => {
    vi.mocked(integrationService.getStatus).mockResolvedValue({
      connected_services: ['google_drive'],
      missing_services: ['dataverse'],
    });
    vi.mocked(integrationService.getIntegrations).mockResolvedValue({
      integrations: [
        {
          id: 1,
          service_name: 'google_drive',
          expires_at: null,
          scopes: null,
          is_connected: true,
          is_expired: false,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      count: 1,
    });
    vi.mocked(integrationService.getSupportedServices).mockResolvedValue({
      services: ['google_drive', 'dataverse'],
    });

    render(<IntegrationSettings />);

    await waitFor(() => {
      expect(screen.getByText('Google Drive')).toBeInTheDocument();
    });

    expect(screen.getByText('Dataverse')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Not Connected')).toBeInTheDocument();
  });

  it('shows connect button for disconnected services', async () => {
    vi.mocked(integrationService.getStatus).mockResolvedValue({
      connected_services: [],
      missing_services: ['google_drive'],
    });
    vi.mocked(integrationService.getIntegrations).mockResolvedValue({
      integrations: [],
      count: 0,
    });
    vi.mocked(integrationService.getSupportedServices).mockResolvedValue({
      services: ['google_drive'],
    });

    render(<IntegrationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument();
    });
  });

  it('shows disconnect button for connected services', async () => {
    vi.mocked(integrationService.getStatus).mockResolvedValue({
      connected_services: ['google_drive'],
      missing_services: [],
    });
    vi.mocked(integrationService.getIntegrations).mockResolvedValue({
      integrations: [
        {
          id: 1,
          service_name: 'google_drive',
          expires_at: null,
          scopes: null,
          is_connected: true,
          is_expired: false,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      count: 1,
    });
    vi.mocked(integrationService.getSupportedServices).mockResolvedValue({
      services: ['google_drive'],
    });

    render(<IntegrationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /disconnect/i })).toBeInTheDocument();
    });
  });

  it('calls startOAuth when connect is clicked', async () => {
    const user = userEvent.setup();

    vi.mocked(integrationService.getStatus).mockResolvedValue({
      connected_services: [],
      missing_services: ['google_drive'],
    });
    vi.mocked(integrationService.getIntegrations).mockResolvedValue({
      integrations: [],
      count: 0,
    });
    vi.mocked(integrationService.getSupportedServices).mockResolvedValue({
      services: ['google_drive'],
    });
    vi.mocked(integrationService.startOAuth).mockResolvedValue({
      authorization_url: 'https://accounts.google.com/oauth',
      service: 'google_drive',
    });

    render(<IntegrationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /connect/i }));

    await waitFor(() => {
      expect(integrationService.startOAuth).toHaveBeenCalledWith('google_drive');
    });
  });

  it('calls disconnect and reloads data', async () => {
    const user = userEvent.setup();

    vi.mocked(integrationService.getStatus).mockResolvedValue({
      connected_services: ['google_drive'],
      missing_services: [],
    });
    vi.mocked(integrationService.getIntegrations).mockResolvedValue({
      integrations: [
        {
          id: 1,
          service_name: 'google_drive',
          expires_at: null,
          scopes: null,
          is_connected: true,
          is_expired: false,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      count: 1,
    });
    vi.mocked(integrationService.getSupportedServices).mockResolvedValue({
      services: ['google_drive'],
    });
    vi.mocked(integrationService.disconnect).mockResolvedValue();

    render(<IntegrationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /disconnect/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /disconnect/i }));

    await waitFor(() => {
      expect(integrationService.disconnect).toHaveBeenCalledWith('google_drive');
    });
  });

  it('displays error message on API failure', async () => {
    vi.mocked(integrationService.getStatus).mockRejectedValue(new Error('API Error'));
    vi.mocked(integrationService.getIntegrations).mockRejectedValue(new Error('API Error'));
    vi.mocked(integrationService.getSupportedServices).mockRejectedValue(new Error('API Error'));

    render(<IntegrationSettings />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });
});
