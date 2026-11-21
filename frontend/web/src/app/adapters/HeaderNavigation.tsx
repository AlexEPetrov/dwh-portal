import { pluginRegistry } from '@asset-management/app-shell/plugin';
import {
    HEADER_NAVIGATION_CONTRIBUTION,
    type HeaderNavigationItem,
} from '@shared/plugins/headerNavigation';
import { theme } from 'antd';
import type { CSSProperties } from 'react';
import { NavLink } from 'react-router-dom';

export function HeaderNavigation() {
  const { token } = theme.useToken();
  // Discovery publishes enabled modules before the application router renders.
  const items = Object.entries(
    pluginRegistry.getContributions<HeaderNavigationItem>(HEADER_NAVIGATION_CONTRIBUTION),
  ).sort(([keyA, a], [keyB, b]) =>
    (a.order ?? 0) - (b.order ?? 0) || keyA.localeCompare(keyB),
  );

  if (!items.length) return null;

  return (
    <nav
      aria-label="Быстрые переходы"
      className="portal-header-navigation"
      style={{
        '--header-nav-text': token.colorTextSecondary,
        '--header-nav-active': token.colorText,
        '--header-nav-hover': token.colorFillTertiary,
        '--header-nav-accent': token.colorPrimary,
      } as CSSProperties}
    >
      {items.map(([key, item]) => (
        <NavLink
          key={key}
          to={item.path}
          className={({ isActive }) => `portal-header-navigation__link${isActive ? ' is-active' : ''}`}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
