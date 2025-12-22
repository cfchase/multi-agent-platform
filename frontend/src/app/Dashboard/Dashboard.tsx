import * as React from 'react';
import { PageSection, Title, Button, Alert, AlertVariant } from '@patternfly/react-core';
import axios from 'axios';

const Dashboard: React.FunctionComponent = () => {
  const [healthStatus, setHealthStatus] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    setHealthStatus(null);
    
    try {
      const response = await axios.get('/api/v1/utils/health-check');
      setHealthStatus(response.data.status || 'OK');
    } catch (err) {
      setError('Failed to connect to backend');
      console.error('Health check failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageSection hasBodyWrapper={false}>
      <Title headingLevel="h1" size="lg">Dashboard Page Title!</Title>
      <div style={{ marginTop: '20px' }}>
        <Button onClick={checkHealth} isLoading={loading} isDisabled={loading}>
          Check Backend Health
        </Button>
        {healthStatus && (
          <Alert variant={AlertVariant.success} title="Backend is healthy" style={{ marginTop: '10px' }}>
            Status: {healthStatus}
          </Alert>
        )}
        {error && (
          <Alert variant={AlertVariant.danger} title="Health check failed" style={{ marginTop: '10px' }}>
            {error}
          </Alert>
        )}
      </div>
    </PageSection>
  );
};

export { Dashboard };
