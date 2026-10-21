import { createAppTheme, type AppColorMode } from '@asset-management/ui-kit/theme';
import { ConfigProvider, type ThemeConfig } from 'antd';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';

type ThemeModeContextValue = {
  preference: ThemePreference;
  resolvedMode: AppColorMode;
  setPreference: (preference: ThemePreference) => void;
};

const STORAGE_KEY = 'asset-management.theme-mode';
const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);

const readStoredPreference = (): ThemePreference => {
  if (typeof window === 'undefined') {
    return 'system';
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw === 'light' || raw === 'dark' || raw === 'system') {
    return raw;
  }
  return 'system';
};

const systemPrefersDark = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-color-scheme: dark)').matches;

export type ThemeModeProviderProps = {
  children: ReactNode;
  /** Optional static theme override; skips day/night switching when set. */
  theme?: ThemeConfig;
};

export function ThemeModeProvider({ children, theme }: ThemeModeProviderProps) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredPreference());
  const [systemDark, setSystemDark] = useState(() => systemPrefersDark());

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setSystemDark(media.matches);
    onChange();
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const resolvedMode: AppColorMode =
    preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = resolvedMode;
    root.style.colorScheme = resolvedMode;
  }, [resolvedMode]);

  const activeTheme = useMemo(
    () => theme ?? createAppTheme(resolvedMode),
    [theme, resolvedMode]
  );

  const value = useMemo(
    () => ({
      preference,
      resolvedMode,
      setPreference,
    }),
    [preference, resolvedMode, setPreference]
  );

  return (
    <ThemeModeContext.Provider value={value}>
      <ConfigProvider theme={activeTheme}>{children}</ConfigProvider>
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode(): ThemeModeContextValue {
  const context = useContext(ThemeModeContext);
  if (!context) {
    throw new Error('useThemeMode must be used within ThemeModeProvider');
  }
  return context;
}

/** Safe for chrome that may render outside the provider during bootstrap. */
export function useOptionalThemeMode(): ThemeModeContextValue | null {
  return useContext(ThemeModeContext);
}
