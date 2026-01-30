import * as React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Button,
  Dropdown,
  DropdownItem,
  DropdownList,
  Masthead,
  MastheadBrand,
  MastheadContent,
  MastheadLogo,
  MastheadMain,
  MastheadToggle,
  MenuToggle,
  Nav,
  NavExpandable,
  NavItem,
  NavList,
  Page,
  PageSidebar,
  PageSidebarBody,
  SkipToContent,
  Spinner,
  Toolbar,
  ToolbarContent,
  ToolbarGroup,
  ToolbarItem,
} from '@patternfly/react-core';
import { IAppRoute, IAppRouteGroup, routes } from '@app/routeConfig';
import { AdjustIcon, BarsIcon, MoonIcon, OutlinedCommentsIcon, SunIcon } from '@patternfly/react-icons';
import { useApp } from '@app/contexts/AppContext';
import { userService } from '@app/services/userService';

interface IAppLayout {
  children: React.ReactNode;
}

const AppLayout: React.FunctionComponent<IAppLayout> = ({ children }) => {
  const { currentUser, isLoadingUser } = useApp();
  const [sidebarOpen, setSidebarOpen] = React.useState(true);
  const [isUserMenuOpen, setIsUserMenuOpen] = React.useState(false);
  type ThemeMode = 'system' | 'light' | 'dark';
  const [themeMode, setThemeMode] = React.useState<ThemeMode>(() => {
    const saved = localStorage.getItem('theme') as ThemeMode | null;
    return saved && ['system', 'light', 'dark'].includes(saved) ? saved : 'system';
  });

  React.useEffect(() => {
    const root = document.documentElement;
    const applyTheme = (isDark: boolean) => {
      if (isDark) {
        root.classList.add('pf-v6-theme-dark');
      } else {
        root.classList.remove('pf-v6-theme-dark');
      }
    };

    localStorage.setItem('theme', themeMode);

    if (themeMode === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      applyTheme(mediaQuery.matches);
      const handler = (e: MediaQueryListEvent) => applyTheme(e.matches);
      mediaQuery.addEventListener('change', handler);
      return () => mediaQuery.removeEventListener('change', handler);
    } else {
      applyTheme(themeMode === 'dark');
    }
  }, [themeMode]);

  const cycleTheme = () => {
    setThemeMode((current) => {
      if (current === 'system') return 'light';
      if (current === 'light') return 'dark';
      return 'system';
    });
  };

  // Icons represent the CURRENT mode (PatternFly convention)
  // AdjustIcon (half light/dark) for system, SunIcon for light, MoonIcon for dark
  const themeIcon = themeMode === 'system' ? <AdjustIcon /> : themeMode === 'light' ? <SunIcon /> : <MoonIcon />;
  const themeLabel = themeMode === 'system' ? 'System theme' : themeMode === 'light' ? 'Light mode' : 'Dark mode';

  const handleLogout = () => {
    setIsUserMenuOpen(false);
    userService.logout();
  };

  const masthead = (
    <Masthead>
      <MastheadMain>
        <MastheadToggle>
          <Button
            icon={<BarsIcon />}
            variant="plain"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Global navigation"
          />
        </MastheadToggle>
        <MastheadBrand data-codemods>
          <MastheadLogo data-codemods>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <OutlinedCommentsIcon style={{ fontSize: '28px', color: 'var(--pf-t--global--color--brand--default)' }} />
              <span style={{ fontSize: '20px', fontWeight: 600, color: 'var(--pf-t--global--text--color--regular)' }}>
                Chat
              </span>
            </span>
          </MastheadLogo>
        </MastheadBrand>
      </MastheadMain>
      <MastheadContent>
        <Toolbar id="masthead-toolbar" isStatic>
          <ToolbarContent>
            <ToolbarGroup variant="action-group-plain" align={{ default: 'alignEnd' }}>
              <ToolbarItem>
                <Button
                  variant="plain"
                  aria-label={themeLabel}
                  onClick={cycleTheme}
                  icon={themeIcon}
                />
              </ToolbarItem>
              <ToolbarItem>
                {isLoadingUser ? (
                  <Spinner size="md" aria-label="Loading user information" />
                ) : (
                  <Dropdown
                    popperProps={{ position: 'right' }}
                    onOpenChange={(isOpen) => setIsUserMenuOpen(isOpen)}
                    toggle={(toggleRef) => (
                      <MenuToggle
                        aria-label="User menu"
                        id="user-menu-toggle"
                        ref={toggleRef}
                        onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                        isExpanded={isUserMenuOpen}
                      >
                        {currentUser?.email || currentUser?.username || 'Unknown'}
                      </MenuToggle>
                    )}
                    isOpen={isUserMenuOpen}
                  >
                    <DropdownList>
                      <DropdownItem key="logout" onClick={handleLogout}>
                        Log out
                      </DropdownItem>
                    </DropdownList>
                  </Dropdown>
                )}
              </ToolbarItem>
            </ToolbarGroup>
          </ToolbarContent>
        </Toolbar>
      </MastheadContent>
    </Masthead>
  );

  const location = useLocation();

  const renderNavItem = (route: IAppRoute, index: number) => (
    <NavItem key={`${route.label}-${index}`} id={`${route.label}-${index}`} isActive={route.path === location.pathname}>
      <NavLink
        to={route.path}
      >
        {route.label}
      </NavLink>
    </NavItem>
  );

  const renderNavGroup = (group: IAppRouteGroup, groupIndex: number) => (
    <NavExpandable
      key={`${group.label}-${groupIndex}`}
      id={`${group.label}-${groupIndex}`}
      title={group.label}
      isActive={group.routes.some((route) => route.path === location.pathname)}
    >
      {group.routes.map((route, idx) => route.label && renderNavItem(route, idx))}
    </NavExpandable>
  );

  const Navigation = (
    <Nav id="nav-primary-simple">
      <NavList id="nav-list-simple">
        {routes.map(
          (route, idx) => route.label && (!route.routes ? renderNavItem(route, idx) : renderNavGroup(route, idx)),
        )}
      </NavList>
    </Nav>
  );

  const Sidebar = (
    <PageSidebar>
      <PageSidebarBody>{Navigation}</PageSidebarBody>
    </PageSidebar>
  );

  const pageId = 'primary-app-container';

  const PageSkipToContent = (
    <SkipToContent
      onClick={(event) => {
        event.preventDefault();
        const primaryContentContainer = document.getElementById(pageId);
        primaryContentContainer?.focus();
      }}
      href={`#${pageId}`}
    >
      Skip to Content
    </SkipToContent>
  );
  return (
    <Page
      mainContainerId={pageId}
      masthead={masthead}
      sidebar={sidebarOpen && Sidebar}
      skipToContent={PageSkipToContent}
    >
      {children}
    </Page>
  );
};

export { AppLayout };
