import * as React from 'react';
import '@patternfly/react-core/dist/styles/base.css';
import { BrowserRouter as Router } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from '@app/AppLayout/AppLayout';
import { AppRoutes } from '@app/routes';
import { AppProvider } from '@app/contexts/AppContext';
import { ToastProvider } from '@app/contexts/ToastContext';
import '@app/app.css';

// Configure React Query with sensible defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const App: React.FunctionComponent = () => (
  <QueryClientProvider client={queryClient}>
    <Router>
      <AppProvider>
        <ToastProvider>
          <AppLayout>
            <AppRoutes />
          </AppLayout>
        </ToastProvider>
      </AppProvider>
    </Router>
  </QueryClientProvider>
);

export default App;
