import { theme, type ThemeConfig } from 'antd';

export type AppColorMode = 'light' | 'dark';

const brandToken: ThemeConfig['token'] = {
  colorPrimary: '#2563eb',
  colorSuccess: '#10b981',
  colorWarning: '#f59e0b',
  colorError: '#ef4444',
  colorInfo: '#2563eb',
  fontSize: 14,
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  borderRadius: 8,
  borderRadiusLG: 14,
  wireframe: false,
};

const lightComponents: ThemeConfig['components'] = {
  Layout: {
    headerBg: 'rgba(255,255,255,0.88)',
    siderBg: '#fbfcfe',
    bodyBg: '#f4f7fb',
  },
  Menu: {
    itemBg: 'transparent',
    itemColor: '#64748b',
    itemBorderRadius: 10,
    itemMarginInline: 8,
    itemMarginBlock: 4,
    itemHoverColor: '#2563eb',
    itemSelectedBg: '#eaf2ff',
    itemSelectedColor: '#1d4ed8',
    itemHoverBg: '#eff6ff',
    itemActiveBg: '#eaf2ff',
    subMenuItemBg: 'transparent',
  },
  Table: {
    headerBg: '#f8fafc',
    headerColor: '#1e293b',
    rowHoverBg: '#f8fafc',
    borderColor: '#e2e8f0',
  },
  Card: {
    boxShadow: '0 10px 30px rgba(15, 23, 42, 0.06)',
    headerBg: 'transparent',
  },
  Button: {
    borderRadius: 8,
    controlHeight: 38,
    primaryShadow: 'none',
    defaultShadow: 'none',
  },
  Input: {
    borderRadius: 8,
    controlHeight: 38,
    hoverBorderColor: '#60a5fa',
    activeBorderColor: '#2563eb',
  },
  Select: {
    borderRadius: 8,
    controlHeight: 38,
    optionSelectedBg: '#eff6ff',
  },
  DatePicker: {
    borderRadius: 8,
    controlHeight: 38,
    hoverBorderColor: '#60a5fa',
    activeBorderColor: '#2563eb',
  },
  Dropdown: {
    paddingBlock: 6,
  },
};

const darkComponents: ThemeConfig['components'] = {
  Layout: {
    headerBg: 'rgba(15, 23, 42, 0.88)',
    siderBg: '#0b1220',
    bodyBg: '#020617',
  },
  Menu: {
    itemBg: 'transparent',
    itemColor: '#94a3b8',
    itemBorderRadius: 10,
    itemMarginInline: 8,
    itemMarginBlock: 4,
    itemHoverColor: '#93c5fd',
    itemSelectedBg: 'rgba(37, 99, 235, 0.22)',
    itemSelectedColor: '#bfdbfe',
    itemHoverBg: 'rgba(148, 163, 184, 0.08)',
    itemActiveBg: 'rgba(37, 99, 235, 0.22)',
    subMenuItemBg: 'transparent',
    darkItemBg: 'transparent',
  },
  Table: {
    headerBg: '#111827',
    headerColor: '#e2e8f0',
    rowHoverBg: '#111827',
    borderColor: '#1f2937',
  },
  Card: {
    colorBgContainer: '#0f172a',
    boxShadow: '0 12px 32px rgba(0, 0, 0, 0.35)',
    headerBg: 'transparent',
  },
  Tag: {
    defaultBg: 'rgba(148, 163, 184, 0.14)',
    defaultColor: '#e2e8f0',
  },
  Button: {
    borderRadius: 8,
    controlHeight: 38,
    primaryShadow: 'none',
    defaultShadow: 'none',
  },
  Input: {
    colorBgContainer: '#1e293b',
    colorText: '#e2e8f0',
    colorTextPlaceholder: '#64748b',
    borderRadius: 8,
    controlHeight: 38,
    hoverBorderColor: '#60a5fa',
    activeBorderColor: '#3b82f6',
  },
  Select: {
    colorBgContainer: '#1e293b',
    colorText: '#e2e8f0',
    colorTextPlaceholder: '#64748b',
    optionSelectedBg: 'rgba(37, 99, 235, 0.28)',
    borderRadius: 8,
    controlHeight: 38,
  },
  DatePicker: {
    borderRadius: 8,
    controlHeight: 38,
    hoverBorderColor: '#60a5fa',
    activeBorderColor: '#3b82f6',
  },
  Dropdown: {
    paddingBlock: 6,
  },
};

/** Build the shared Ant Design theme for light or dark mode. */
export const createAppTheme = (mode: AppColorMode = 'light'): ThemeConfig => {
  const isDark = mode === 'dark';
  return {
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      ...brandToken,
      ...(isDark
        ? {
            colorBgLayout: '#020617',
            colorBgContainer: '#0f172a',
            colorBgElevated: '#1e293b',
            colorBorder: '#334155',
            colorBorderSecondary: '#1f2937',
            colorText: '#e2e8f0',
            colorTextSecondary: '#94a3b8',
            colorTextTertiary: '#64748b',
            colorFillSecondary: 'rgba(148, 163, 184, 0.12)',
            colorFillTertiary: 'rgba(148, 163, 184, 0.08)',
          }
        : {
            colorBgLayout: '#f4f7fb',
            colorBgContainer: '#ffffff',
            colorBorderSecondary: '#e2e8f0',
            colorText: '#0f172a',
            colorTextSecondary: '#475569',
          }),
    },
    components: isDark ? darkComponents : lightComponents,
  };
};

/** Default light theme (backward-compatible export). */
export const appTheme: ThemeConfig = createAppTheme('light');
