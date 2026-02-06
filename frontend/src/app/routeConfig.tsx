import * as React from 'react';

import { Chat } from '@app/Chat/Chat';
import { GeneralSettings } from '@app/Settings/General/GeneralSettings';
import { IntegrationSettings } from '@app/Settings/Integrations/IntegrationSettings';
import { ProfileSettings } from '@app/Settings/Profile/ProfileSettings';

// =============================================================================
// Types
// =============================================================================

export interface IAppRoute {
  label?: string; // Excluding the label will exclude the route from the nav sidebar in AppLayout
  element: React.ReactElement;
  exact?: boolean;
  path: string;
  title: string;
  routes?: undefined;
}

export interface IAppRouteGroup {
  label: string;
  routes: IAppRoute[];
}

export type AppRouteConfig = IAppRoute | IAppRouteGroup;

// =============================================================================
// Route Configuration
// =============================================================================

export const routes: AppRouteConfig[] = [
  {
    element: <Chat />,
    exact: true,
    label: 'Chat',
    path: '/',
    title: 'Multi-Agent Platform | Chat',
  },
  {
    label: 'Settings',
    routes: [
      {
        element: <GeneralSettings />,
        exact: true,
        path: '/settings/general',
        title: 'Multi-Agent Platform | General Settings',
      },
      {
        element: <ProfileSettings />,
        exact: true,
        path: '/settings/profile',
        title: 'Multi-Agent Platform | Profile Settings',
      },
      {
        element: <IntegrationSettings />,
        exact: true,
        label: 'Integrations',
        path: '/settings/integrations',
        title: 'Multi-Agent Platform | Integration Settings',
      },
    ],
  },
];

// =============================================================================
// Utilities
// =============================================================================

function flattenRoutes(routeConfigs: AppRouteConfig[]): IAppRoute[] {
  return routeConfigs.reduce<IAppRoute[]>((flattened, route) => {
    if (route.routes) {
      return [...flattened, ...route.routes];
    }
    return [...flattened, route];
  }, []);
}

export const flattenedRoutes: IAppRoute[] = flattenRoutes(routes);