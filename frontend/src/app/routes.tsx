import * as React from 'react';
import { Route, Routes } from 'react-router-dom';
import { NotFound } from '@app/NotFound/NotFound';
import { flattenedRoutes } from './routeConfig';

const AppRoutes = (): React.ReactElement => (
  <Routes>
    {flattenedRoutes.map(({ path, element }, idx) => (
      <Route path={path} element={element} key={idx} />
    ))}
    <Route element={<NotFound />} />
  </Routes>
);

export { AppRoutes };
