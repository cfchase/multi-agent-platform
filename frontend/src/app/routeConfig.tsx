import * as React from 'react';
// import { Dashboard } from '@app/Dashboard/Dashboard';
import { Chat } from '@app/Chat/Chat';
import { GeneralSettings } from '@app/Settings/General/GeneralSettings';
import { ProfileSettings } from '@app/Settings/Profile/ProfileSettings';

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

export const routes: AppRouteConfig[] = [
  // {
  //   element: <Dashboard />,
  //   exact: true,
  //   label: 'Dashboard',
  //   path: '/',
  //   title: 'PatternFly Seed | Main Dashboard',
  // },
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
        label: 'General',
        path: '/settings/general',
        title: 'PatternFly Seed | General Settings',
      },
      {
        element: <ProfileSettings />,
        exact: true,
        label: 'Profile',
        path: '/settings/profile',
        title: 'PatternFly Seed | Profile Settings',
      },
    ],
  },
];

export const flattenedRoutes: IAppRoute[] = routes.reduce(
  (flattened, route) => [...flattened, ...(route.routes ? route.routes : [route])],
  [] as IAppRoute[],
);