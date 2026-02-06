import { useState, useEffect, useCallback } from 'react';
import type { FC } from 'react';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  EmptyState,
  Flex,
  FlexItem,
  Icon,
  Label,
  PageSection,
  Spinner,
  Stack,
  StackItem,
  Title,
} from '@patternfly/react-core';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  LinkIcon,
  UnlinkIcon,
} from '@patternfly/react-icons';
import { useDocumentTitle } from '@app/utils/useDocumentTitle';
import {
  integrationService,
  IntegrationStatusResponse,
  Integration,
} from '@app/services/integrationService';

interface ServiceCardProps {
  serviceName: string;
  isConnected: boolean;
  isExpired?: boolean;
  expiresAt?: string | null;
  onConnect: (serviceName: string) => void;
  onDisconnect: (serviceName: string) => void;
  isLoading: boolean;
}

const ServiceCard: FC<ServiceCardProps> = ({
  serviceName,
  isConnected,
  isExpired,
  expiresAt,
  onConnect,
  onDisconnect,
  isLoading,
}) => {
  const displayName = integrationService.getServiceDisplayName(serviceName);
  const description = integrationService.getServiceDescription(serviceName);

  function getStatusLabel() {
    if (!isConnected) {
      return <Label color="grey">Not Connected</Label>;
    }
    if (isExpired) {
      return <Label color="red">Expired</Label>;
    }
    return <Label color="green">Connected</Label>;
  }

  function getExpiryInfo(): string | null {
    if (!isConnected || !expiresAt) {
      return null;
    }

    const expiryDate = new Date(expiresAt);
    const hoursUntilExpiry = (expiryDate.getTime() - Date.now()) / (1000 * 60 * 60);

    if (hoursUntilExpiry < 0) {
      return 'Token expired';
    }
    if (hoursUntilExpiry < 24) {
      return `Expires in ${Math.round(hoursUntilExpiry)} hours`;
    }
    return `Expires on ${expiryDate.toLocaleDateString()}`;
  }

  const expiryInfo = getExpiryInfo();

  return (
    <Card isCompact>
      <CardTitle>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
          <FlexItem>
            <Flex gap={{ default: 'gapSm' }} alignItems={{ default: 'alignItemsCenter' }}>
              <FlexItem>
                {isConnected && !isExpired ? (
                  <Icon status="success">
                    <CheckCircleIcon />
                  </Icon>
                ) : (
                  <Icon status="danger">
                    <ExclamationCircleIcon />
                  </Icon>
                )}
              </FlexItem>
              <FlexItem>
                <Title headingLevel="h3" size="md">{displayName}</Title>
              </FlexItem>
              <FlexItem>{getStatusLabel()}</FlexItem>
            </Flex>
          </FlexItem>
          <FlexItem>
            {isConnected ? (
              <Button
                variant="secondary"
                icon={<UnlinkIcon />}
                onClick={() => onDisconnect(serviceName)}
                isLoading={isLoading}
                isDisabled={isLoading}
              >
                Disconnect
              </Button>
            ) : (
              <Button
                variant="primary"
                icon={<LinkIcon />}
                onClick={() => onConnect(serviceName)}
                isLoading={isLoading}
                isDisabled={isLoading}
              >
                Connect
              </Button>
            )}
          </FlexItem>
        </Flex>
      </CardTitle>
      <CardBody>
        <Stack hasGutter>
          <StackItem>
            <p>{description}</p>
          </StackItem>
          {expiryInfo && (
            <StackItem>
              <small>{expiryInfo}</small>
            </StackItem>
          )}
        </Stack>
      </CardBody>
    </Card>
  );
};

const IntegrationSettings: FC = () => {
  useDocumentTitle('Integration Settings');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<IntegrationStatusResponse | null>(null);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [supportedServices, setSupportedServices] = useState<string[]>([]);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusData, integrationsData, servicesData] = await Promise.all([
        integrationService.getStatus(),
        integrationService.getIntegrations(),
        integrationService.getSupportedServices(),
      ]);
      setStatus(statusData);
      setIntegrations(integrationsData.integrations);
      setSupportedServices(servicesData.services);
    } catch (err) {
      console.error('Failed to load integrations:', err);
      setError('Failed to load integrations. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleConnect = async (serviceName: string) => {
    setActionLoading(serviceName);
    try {
      const response = await integrationService.startOAuth(serviceName);
      // Redirect to OAuth provider
      window.location.href = response.authorization_url;
    } catch (err) {
      console.error('Failed to start OAuth:', err);
      setError(`Failed to connect to ${integrationService.getServiceDisplayName(serviceName)}`);
      setActionLoading(null);
    }
  };

  const handleDisconnect = async (serviceName: string) => {
    setActionLoading(serviceName);
    try {
      await integrationService.disconnect(serviceName);
      // Reload data after disconnect
      await loadData();
    } catch (err) {
      console.error('Failed to disconnect:', err);
      setError(`Failed to disconnect from ${integrationService.getServiceDisplayName(serviceName)}`);
    } finally {
      setActionLoading(null);
    }
  };

  function getIntegrationForService(serviceName: string): Integration | undefined {
    return integrations.find((i) => i.service_name === serviceName);
  }

  if (loading) {
    return (
      <PageSection hasBodyWrapper={false}>
        <EmptyState>
          <Spinner size="xl" />
          <Title headingLevel="h2" size="lg">
            Loading integrations...
          </Title>
        </EmptyState>
      </PageSection>
    );
  }

  return (
    <PageSection hasBodyWrapper={false}>
      <Stack hasGutter>
        <StackItem>
          <Title headingLevel="h1" size="lg">
            External Service Integrations
          </Title>
        </StackItem>

        <StackItem>
          <p>
            Connect your external accounts to enable AI workflows to access your data.
            Your credentials are stored securely and encrypted.
          </p>
        </StackItem>

        {error && (
          <StackItem>
            <Alert
              variant="danger"
              title="Error"
              actionClose={<Button variant="plain" onClick={() => setError(null)}>Dismiss</Button>}
            >
              {error}
            </Alert>
          </StackItem>
        )}

        <StackItem>
          <Stack hasGutter>
            {supportedServices.map((serviceName) => {
              const integration = getIntegrationForService(serviceName);
              const isConnected = status?.connected_services.includes(serviceName) ?? false;
              const isExpired = status?.expired_services?.includes(serviceName) ?? false;
              // A service has a token stored if it's either connected or expired
              const hasToken = isConnected || isExpired;

              return (
                <StackItem key={serviceName}>
                  <ServiceCard
                    serviceName={serviceName}
                    isConnected={hasToken}
                    isExpired={isExpired}
                    expiresAt={integration?.expires_at}
                    onConnect={handleConnect}
                    onDisconnect={handleDisconnect}
                    isLoading={actionLoading === serviceName}
                  />
                </StackItem>
              );
            })}
          </Stack>
        </StackItem>

        {supportedServices.length === 0 && (
          <StackItem>
            <EmptyState>
              <Title headingLevel="h2" size="lg">
                No integrations available
              </Title>
              <p>There are no external services configured for this installation.</p>
            </EmptyState>
          </StackItem>
        )}
      </Stack>
    </PageSection>
  );
};

export { IntegrationSettings };
