import { DesktopOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons';
import { Segmented, Tooltip } from 'antd';
import type { ReactNode } from 'react';
import { useOptionalThemeMode, type ThemePreference } from './ThemeModeProvider';

const OPTIONS: Array<{ value: ThemePreference; icon: ReactNode; title: string }> = [
  { value: 'light', icon: <SunOutlined />, title: 'День' },
  { value: 'system', icon: <DesktopOutlined />, title: 'Как в системе' },
  { value: 'dark', icon: <MoonOutlined />, title: 'Ночь' },
];

/** Compact Ant Design day/night control for the application header. */
export function ThemeModeControl() {
  const themeMode = useOptionalThemeMode();
  if (!themeMode) {
    return null;
  }

  return (
    <Tooltip title="Тема оформления">
      <Segmented
        size="small"
        value={themeMode.preference}
        onChange={(value) => themeMode.setPreference(value as ThemePreference)}
        options={OPTIONS.map((option) => ({
          value: option.value,
          icon: option.icon,
          title: option.title,
        }))}
        aria-label="Тема оформления"
      />
    </Tooltip>
  );
}
