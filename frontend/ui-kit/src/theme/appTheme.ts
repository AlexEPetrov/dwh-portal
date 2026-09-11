import { theme, type ThemeConfig } from 'antd';

export const appTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#2563eb',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#2563eb',
    colorBgLayout: '#f4f7fb',
    colorBgContainer: '#ffffff',
    colorBorderSecondary: '#e2e8f0',
    colorText: '#0f172a',
    colorTextSecondary: '#475569',
    fontSize: 14,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    borderRadius: 8,
    borderRadiusLG: 14,
    wireframe: false,
  },
  components: {
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
  },
};
