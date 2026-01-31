import * as React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Button,
  Dropdown,
  DropdownItem,
  DropdownList,
  Flex,
  FlexItem,
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

interface AppLayoutProps {
  children: React.ReactNode;
}

type ThemeMode = 'system' | 'light' | 'dark';

const VALID_THEME_MODES: ThemeMode[] = ['system', 'light', 'dark'];
const DARK_THEME_CLASS = 'pf-v6-theme-dark';
const THEME_STORAGE_KEY = 'theme';
const PAGE_CONTAINER_ID = 'primary-app-container';

function getThemeIcon(mode: ThemeMode): React.ReactNode {
  switch (mode) {
    case 'system':
      return <AdjustIcon />;
    case 'light':
      return <SunIcon />;
    case 'dark':
      return <MoonIcon />;
  }
}

function getThemeLabel(mode: ThemeMode): string {
  switch (mode) {
    case 'system':
      return 'System theme';
    case 'light':
      return 'Light mode';
    case 'dark':
      return 'Dark mode';
  }
}

function getNextThemeMode(current: ThemeMode): ThemeMode {
  switch (current) {
    case 'system':
      return 'light';
    case 'light':
      return 'dark';
    case 'dark':
      return 'system';
  }
}

function getInitialThemeMode(): ThemeMode {
  const saved = localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
  return saved && VALID_THEME_MODES.includes(saved) ? saved : 'system';
}

function applyThemeClass(isDark: boolean): void {
  const root = document.documentElement;
  if (isDark) {
    root.classList.add(DARK_THEME_CLASS);
  } else {
    root.classList.remove(DARK_THEME_CLASS);
  }
}

function AppLayout({ children }: AppLayoutProps): React.ReactElement {
  const { currentUser, isLoadingUser } = useApp();
  const [sidebarOpen, setSidebarOpen] = React.useState(true);
  const [isUserMenuOpen, setIsUserMenuOpen] = React.useState(false);
  const [themeMode, setThemeMode] = React.useState<ThemeMode>(getInitialThemeMode);

  React.useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, themeMode);

    if (themeMode === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      applyThemeClass(mediaQuery.matches);
      const handler = (e: MediaQueryListEvent) => applyThemeClass(e.matches);
      mediaQuery.addEventListener('change', handler);
      return () => mediaQuery.removeEventListener('change', handler);
    }

    applyThemeClass(themeMode === 'dark');
  }, [themeMode]);

  const cycleTheme = () => setThemeMode(getNextThemeMode);

  const themeIcon = getThemeIcon(themeMode);
  const themeLabel = getThemeLabel(themeMode);

  const handleLogout = () => {
    setIsUserMenuOpen(false);
    userService.logout();
  };

  const userDisplayName = currentUser?.email || currentUser?.username || 'Unknown';

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
          <MastheadLogo data-codemods component="div">
            <Flex alignItems={{ default: 'alignItemsCenter' }} gap={{ default: 'gapSm' }}>
              <FlexItem>
                <OutlinedCommentsIcon className="pf-v6-u-font-size-2xl pf-v6-u-color-brand-default" />
              </FlexItem>
              <FlexItem>
                <span className="pf-v6-u-font-size-xl pf-v6-u-font-weight-bold">Chat</span>
              </FlexItem>
            </Flex>
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
                        {userDisplayName}
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

  function renderNavItem(route: IAppRoute, index: number): React.ReactElement {
    const itemId = `${route.label}-${index}`;
    return (
      <NavItem key={itemId} id={itemId} isActive={route.path === location.pathname}>
        <NavLink to={route.path}>{route.label}</NavLink>
      </NavItem>
    );
  }

  function renderNavGroup(group: IAppRouteGroup, groupIndex: number): React.ReactElement {
    const groupId = `${group.label}-${groupIndex}`;
    const isActive = group.routes.some((route) => route.path === location.pathname);
    return (
      <NavExpandable key={groupId} id={groupId} title={group.label} isActive={isActive}>
        {group.routes.map((route, idx) => route.label && renderNavItem(route, idx))}
      </NavExpandable>
    );
  }

  const navigation = (
    <Nav id="nav-primary-simple">
      <NavList id="nav-list-simple">
        {routes.map((route, idx) =>
          route.label && (route.routes ? renderNavGroup(route, idx) : renderNavItem(route, idx))
        )}
      </NavList>
    </Nav>
  );

  const sidebar = (
    <PageSidebar>
      <PageSidebarBody>{navigation}</PageSidebarBody>
    </PageSidebar>
  );

  const handleSkipToContent = (event: React.MouseEvent) => {
    event.preventDefault();
    document.getElementById(PAGE_CONTAINER_ID)?.focus();
  };

  const pageSkipToContent = (
    <SkipToContent onClick={handleSkipToContent} href={`#${PAGE_CONTAINER_ID}`}>
      Skip to Content
    </SkipToContent>
  );

  return (
    <Page
      mainContainerId={PAGE_CONTAINER_ID}
      masthead={masthead}
      sidebar={sidebarOpen && sidebar}
      skipToContent={pageSkipToContent}
    >
      {children}
    </Page>
  );
}

export { AppLayout };
