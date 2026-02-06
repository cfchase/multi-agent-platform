import * as React from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Alert,
  AlertActionCloseButton,
  AlertGroup,
  AlertVariant,
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
  NotificationBadge,
  NotificationDrawer,
  NotificationDrawerBody,
  NotificationDrawerHeader,
  NotificationDrawerList,
  NotificationDrawerListItem,
  NotificationDrawerListItemBody,
  NotificationDrawerListItemHeader,
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
import { AdjustIcon, BarsIcon, BellIcon, MoonIcon, OutlinedCommentsIcon, SunIcon } from '@patternfly/react-icons';
import { useApp } from '@app/contexts/AppContext';
import { useToast } from '@app/contexts/ToastContext';
import { userService } from '@app/services/userService';
import { integrationService } from '@app/services/integrationService';

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

const INTEGRATION_TOAST_SHOWN_KEY = 'integration-toast-shown';

function AppLayout({ children }: AppLayoutProps): React.ReactElement {
  const { currentUser, isLoadingUser } = useApp();
  const { toasts, addToast, removeToast } = useToast();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = React.useState(true);
  const [isUserMenuOpen, setIsUserMenuOpen] = React.useState(false);
  const [themeMode, setThemeMode] = React.useState<ThemeMode>(getInitialThemeMode);
  const [isNotificationDrawerOpen, setIsNotificationDrawerOpen] = React.useState(false);

  const toggleNotificationDrawer = () => setIsNotificationDrawerOpen(!isNotificationDrawerOpen);

  // Build persistent integration notifications from current user status
  const integrationNotifications = React.useMemo(() => {
    if (!currentUser?.integration_status) return [];

    const notifications: Array<{
      id: string;
      title: string;
      message: string;
      variant: 'warning' | 'danger';
      linkText: string;
      linkHref: string;
    }> = [];

    const { expired, missing } = currentUser.integration_status;

    expired.forEach((service) => {
      notifications.push({
        id: `expired-${service}`,
        title: `${integrationService.getServiceDisplayName(service)} connection expired`,
        message: 'Reconnect to continue using this service.',
        variant: 'danger',
        linkText: 'Reconnect',
        linkHref: '/settings/integrations',
      });
    });

    missing.forEach((service) => {
      notifications.push({
        id: `missing-${service}`,
        title: `${integrationService.getServiceDisplayName(service)} not connected`,
        message: 'Connect your account to enable AI workflows.',
        variant: 'warning',
        linkText: 'Connect',
        linkHref: '/settings/integrations',
      });
    });

    return notifications;
  }, [currentUser?.integration_status]);

  // Determine notification badge variant based on toast count + integration issues
  const notificationCount = toasts.length + integrationNotifications.length;
  const notificationVariant = notificationCount > 0 ? 'attention' : 'read';

  // Show toast notification when user needs to connect integrations
  React.useEffect(() => {
    if (isLoadingUser || !currentUser?.integration_status) return;

    const integrationStatus = currentUser.integration_status;
    const needsAttention =
      integrationStatus.expired.length > 0 || integrationStatus.missing.length > 0;

    // Only show toast once per session
    const alreadyShown = sessionStorage.getItem(INTEGRATION_TOAST_SHOWN_KEY);
    if (needsAttention && !alreadyShown) {
      const expiredServices = integrationStatus.expired.map((s) =>
        integrationService.getServiceDisplayName(s)
      );
      const missingServices = integrationStatus.missing.map((s) =>
        integrationService.getServiceDisplayName(s)
      );

      let message = '';
      if (expiredServices.length > 0 && missingServices.length > 0) {
        message = `${expiredServices.join(', ')} expired. ${missingServices.join(', ')} not connected.`;
      } else if (expiredServices.length > 0) {
        message = `${expiredServices.join(', ')} connection${expiredServices.length > 1 ? 's have' : ' has'} expired.`;
      } else if (missingServices.length > 0) {
        message = `${missingServices.join(', ')} ${missingServices.length > 1 ? 'are' : 'is'} not connected.`;
      }

      addToast({
        title: 'External service connections need attention',
        message: `${message} Connect your accounts to enable AI workflows.`,
        variant: AlertVariant.warning,
        linkText: 'Go to Settings',
        linkHref: '/settings/integrations',
      });

      sessionStorage.setItem(INTEGRATION_TOAST_SHOWN_KEY, 'true');
    }
  }, [currentUser, isLoadingUser, addToast]);

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
                <NotificationBadge
                  icon={<BellIcon />}
                  variant={notificationVariant}
                  count={notificationCount}
                  onClick={toggleNotificationDrawer}
                  aria-label="Notifications"
                  isExpanded={isNotificationDrawerOpen}
                />
              </ToolbarItem>
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

  const hasNotifications = integrationNotifications.length > 0 || toasts.length > 0;

  const notificationDrawerPanel = (
    <NotificationDrawer>
      <NotificationDrawerHeader
        count={notificationCount}
        title="Notifications"
        onClose={toggleNotificationDrawer}
      />
      <NotificationDrawerBody>
        {!hasNotifications ? (
          <NotificationDrawerList>
            <NotificationDrawerListItem variant="info" isRead>
              <NotificationDrawerListItemHeader title="No notifications" variant="info" />
              <NotificationDrawerListItemBody>
                You're all caught up!
              </NotificationDrawerListItemBody>
            </NotificationDrawerListItem>
          </NotificationDrawerList>
        ) : (
          <NotificationDrawerList>
            {/* Integration notifications (persistent) */}
            {integrationNotifications.map((notification) => (
              <NotificationDrawerListItem
                key={notification.id}
                variant={notification.variant}
                isRead={false}
              >
                <NotificationDrawerListItemHeader
                  title={notification.title}
                  variant={notification.variant}
                />
                <NotificationDrawerListItemBody>
                  {notification.message}{' '}
                  <a
                    href={notification.linkHref}
                    onClick={(e) => {
                      e.preventDefault();
                      setIsNotificationDrawerOpen(false);
                      navigate(notification.linkHref);
                    }}
                  >
                    {notification.linkText}
                  </a>
                </NotificationDrawerListItemBody>
              </NotificationDrawerListItem>
            ))}
            {/* Ephemeral toasts */}
            {toasts.map((toast) => (
              <NotificationDrawerListItem
                key={toast.id}
                variant={toast.variant === AlertVariant.warning ? 'warning' : toast.variant === AlertVariant.danger ? 'danger' : 'info'}
                isRead={false}
              >
                <NotificationDrawerListItemHeader
                  title={toast.title}
                  variant={toast.variant === AlertVariant.warning ? 'warning' : toast.variant === AlertVariant.danger ? 'danger' : 'info'}
                />
                <NotificationDrawerListItemBody>
                  {toast.message}
                  {toast.linkText && toast.linkHref && (
                    <>
                      {' '}
                      <a
                        href={toast.linkHref}
                        onClick={(e) => {
                          e.preventDefault();
                          removeToast(toast.id);
                          setIsNotificationDrawerOpen(false);
                          navigate(toast.linkHref!);
                        }}
                      >
                        {toast.linkText}
                      </a>
                    </>
                  )}
                </NotificationDrawerListItemBody>
              </NotificationDrawerListItem>
            ))}
          </NotificationDrawerList>
        )}
      </NotificationDrawerBody>
    </NotificationDrawer>
  );

  return (
    <>
      <AlertGroup isToast isLiveRegion>
        {toasts.map((toast) => (
          <Alert
            key={toast.id}
            variant={toast.variant}
            title={toast.title}
            timeout={8000}
            onTimeout={() => removeToast(toast.id)}
            actionClose={<AlertActionCloseButton onClose={() => removeToast(toast.id)} />}
            actionLinks={
              toast.linkText && toast.linkHref ? (
                <a href={toast.linkHref} onClick={() => { removeToast(toast.id); navigate(toast.linkHref!); }}>
                  {toast.linkText}
                </a>
              ) : undefined
            }
          >
            {toast.message}
          </Alert>
        ))}
      </AlertGroup>
      <Page
        mainContainerId={PAGE_CONTAINER_ID}
        masthead={masthead}
        sidebar={sidebarOpen && sidebar}
        skipToContent={pageSkipToContent}
        notificationDrawer={notificationDrawerPanel}
        isNotificationDrawerExpanded={isNotificationDrawerOpen}
        onNotificationDrawerExpand={() => setIsNotificationDrawerOpen(true)}
      >
        {children}
      </Page>
    </>
  );
}

export { AppLayout };
