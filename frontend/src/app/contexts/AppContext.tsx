import * as React from 'react';
import { userService, CurrentUser, HealthCheckResponse } from '@app/services/userService';

interface AppContextType {
  currentUser: CurrentUser | null;
  isLoadingUser: boolean;
  healthCheck: HealthCheckResponse | null;
  isLoadingHealthCheck: boolean;
}

const AppContext = React.createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = React.useState<CurrentUser | null>(null);
  const [isLoadingUser, setIsLoadingUser] = React.useState(true);
  const [healthCheck, setHealthCheck] = React.useState<HealthCheckResponse | null>(null);
  const [isLoadingHealthCheck, setIsLoadingHealthCheck] = React.useState(true);

  React.useEffect(() => {
    // AbortController to prevent state updates on unmounted component
    const abortController = new AbortController();
    let isMounted = true;

    const fetchCurrentUser = async () => {
      try {
        const userData = await userService.getCurrentUser();
        if (isMounted) {
          setCurrentUser(userData);
        }
      } catch (error) {
        if (isMounted && !abortController.signal.aborted) {
          console.error('Failed to fetch current user:', error);
          setCurrentUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoadingUser(false);
        }
      }
    };

    const fetchHealthCheck = async () => {
      try {
        const healthData = await userService.getHealthCheck();
        if (isMounted) {
          setHealthCheck(healthData);
        }
      } catch (error) {
        if (isMounted && !abortController.signal.aborted) {
          console.error('Failed to fetch health check:', error);
          setHealthCheck(null);
        }
      } finally {
        if (isMounted) {
          setIsLoadingHealthCheck(false);
        }
      }
    };

    fetchCurrentUser();
    fetchHealthCheck();

    // Cleanup function to prevent state updates after unmount
    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, []);

  return (
    <AppContext.Provider value={{ currentUser, isLoadingUser, healthCheck, isLoadingHealthCheck }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = (): AppContextType => {
  const context = React.useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
