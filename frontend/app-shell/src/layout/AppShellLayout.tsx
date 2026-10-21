import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { Drawer, Layout, Tooltip, Typography, theme } from 'antd';
import { useEffect, useRef, useState, type ReactNode } from 'react';

const { Header, Content, Sider } = Layout;
const { Title, Text } = Typography;

export interface AppShellLayoutProps {
  title: ReactNode;
  subtitle?: ReactNode;
  renderSidebar: (collapsed: boolean) => ReactNode;
  headerActions?: ReactNode;
  navigationKey?: string;
  children: ReactNode;
  headerHeight?: number;
  sidebarWidth?: number;
  collapsedSidebarWidth?: number;
  sidebarHoverDelay?: number;
  expandSidebarLabel?: string;
  collapseSidebarLabel?: string;
}

export function AppShellLayout({
  title,
  subtitle,
  renderSidebar,
  headerActions,
  navigationKey,
  children,
  headerHeight = 64,
  sidebarWidth = 260,
  collapsedSidebarWidth = 72,
  sidebarHoverDelay = 1000,
  expandSidebarLabel = 'Expand sidebar',
  collapseSidebarLabel = 'Collapse sidebar',
}: AppShellLayoutProps) {
  const { token } = theme.useToken();
  const [isSiderCollapsed, setIsSiderCollapsed] = useState(false);
  const [isSiderPreviewOpen, setIsSiderPreviewOpen] = useState(false);
  const previewCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewHoverSuppressedUntilRef = useRef(0);

  const clearPreviewCloseTimer = () => {
    if (previewCloseTimerRef.current === null) return;

    clearTimeout(previewCloseTimerRef.current);
    previewCloseTimerRef.current = null;
  };

  const schedulePreviewClose = () => {
    clearPreviewCloseTimer();
    previewCloseTimerRef.current = setTimeout(() => {
      setIsSiderPreviewOpen(false);
      previewCloseTimerRef.current = null;
    }, sidebarHoverDelay);
  };

  const handleSiderLeave = () => {
    previewHoverSuppressedUntilRef.current = 0;
    schedulePreviewClose();
  };

  const handleSiderHover = () => {
    clearPreviewCloseTimer();
    if (isSiderCollapsed && Date.now() >= previewHoverSuppressedUntilRef.current) {
      setIsSiderPreviewOpen(true);
    }
  };

  const handleCollapseToggle = () => {
    const nextCollapsed = !isSiderCollapsed;
    clearPreviewCloseTimer();
    setIsSiderPreviewOpen(false);

    if (nextCollapsed) {
      previewHoverSuppressedUntilRef.current = Date.now() + sidebarHoverDelay;
    } else {
      previewHoverSuppressedUntilRef.current = 0;
    }

    setIsSiderCollapsed(nextCollapsed);
  };

  useEffect(() => {
    setIsSiderPreviewOpen(false);
  }, [navigationKey]);

  useEffect(() => () => clearPreviewCloseTimer(), []);

  return (
    <Layout style={{ height: '100vh', background: token.colorBgLayout }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: token.Layout?.headerBg || token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          padding: '0 24px',
          height: headerHeight,
          flexShrink: 0,
          boxShadow: `0 1px 2px ${token.colorBgSpotlight}14`,
          backdropFilter: 'blur(10px)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Tooltip title={isSiderCollapsed ? expandSidebarLabel : collapseSidebarLabel}>
            <button
              type="button"
              onClick={handleCollapseToggle}
              aria-label={isSiderCollapsed ? expandSidebarLabel : collapseSidebarLabel}
              style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                border: `1px solid ${token.colorBorderSecondary}`,
                background: token.colorBgContainer,
                color: token.colorText,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              {isSiderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </button>
          </Tooltip>

          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', minHeight: 50 }}>
            <Title level={4} style={{ margin: 0, color: token.colorText, fontWeight: 600, lineHeight: 1.7 }}>
              {title}
            </Title>
            {subtitle ? (
              <Text type="secondary" style={{ lineHeight: 1.5 }}>
                {subtitle}
              </Text>
            ) : null}
          </div>
        </div>

        {headerActions ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginLeft: 24 }}>
            {headerActions}
          </div>
        ) : null}
      </Header>

      <Layout style={{ height: `calc(100vh - ${headerHeight}px)`, background: token.colorBgLayout }}>
        <div
          style={{
            position: 'relative',
            width: isSiderCollapsed ? collapsedSidebarWidth : sidebarWidth,
            flex: `0 0 ${isSiderCollapsed ? collapsedSidebarWidth : sidebarWidth}px`,
            height: '100%',
            overflow: 'visible',
            zIndex: 20,
          }}
          onMouseEnter={handleSiderHover}
          onMouseLeave={handleSiderLeave}
        >
          <Sider
            width={isSiderCollapsed ? collapsedSidebarWidth : sidebarWidth}
            collapsedWidth={collapsedSidebarWidth}
            style={{
              background: token.colorBgContainer,
              borderRight: `1px solid ${token.colorBorderSecondary}`,
              boxShadow: 'none',
              height: '100%',
              overflow: 'auto',
            }}
            onMouseEnter={handleSiderHover}
          >
            {renderSidebar(isSiderCollapsed)}
          </Sider>

          {isSiderCollapsed && (
            <Drawer
              open={isSiderPreviewOpen}
              placement="left"
              closable={false}
              mask={false}
              keyboard={false}
              destroyOnClose
              getContainer={false}
              width={sidebarWidth}
              styles={{
                body: { padding: 0, height: '100%' },
                wrapper: { boxShadow: '0 12px 30px rgba(15, 23, 42, 0.12)' },
              }}
              rootStyle={{ position: 'absolute', top: 0, left: 0, height: '100%' }}
              onClose={() => setIsSiderPreviewOpen(false)}
            >
              <div style={{ height: '100%' }} onMouseEnter={handleSiderHover}>
                {renderSidebar(false)}
              </div>
            </Drawer>
          )}
        </div>

        <Content
          style={{
            margin: 0,
            background: token.colorBgLayout,
            padding: token.paddingLG,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'auto',
            height: '100%',
            minHeight: 0,
            boxSizing: 'border-box',
          }}
        >
          <div style={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            {children}
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
