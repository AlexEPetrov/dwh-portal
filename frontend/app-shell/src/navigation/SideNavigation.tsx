import { Menu, theme } from 'antd';
import type { MenuProps } from 'antd';
import type { CSSProperties, ReactNode } from 'react';
import { cloneElement, isValidElement, useEffect, useMemo, useState } from 'react';

export interface SideNavigationItem {
  path: string;
  label: ReactNode;
  icon?: ReactNode;
  strong?: boolean;
  children?: SideNavigationItem[];
}

export interface SideNavigationProps {
  collapsed: boolean;
  currentPath: string;
  items: SideNavigationItem[];
  onNavigate: (path: string) => void;
  defaultOpenKeys?: string[];
}

const renderMenuIcon = (icon: ReactNode): ReactNode => {
  if (!isValidElement(icon)) {
    return icon;
  }

  const typedIcon = icon as React.ReactElement<{ style?: CSSProperties }>;

  return cloneElement(typedIcon, {
    style: {
      fontSize: 22,
      minWidth: 22,
      ...(typedIcon.props.style || {}),
    },
  });
};

const isPathMatch = (currentPath: string, itemPath: string): boolean => {
  if (itemPath === '/') return currentPath === '/';
  return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
};

const flattenItems = (items: SideNavigationItem[]): SideNavigationItem[] =>
  items.flatMap((item) => [item, ...(item.children ? flattenItems(item.children) : [])]);

const toMenuItems = (items: SideNavigationItem[], depth = 0): MenuProps['items'] => items.map((item) => ({
  key: item.path,
  // Preserve the pre-extraction menu behavior: icons are rendered only for
  // top-level navigation entries. Child metadata may still carry an icon,
  // but the legacy SideMenu intentionally did not display it.
  icon: depth === 0 && item.icon ? renderMenuIcon(item.icon) : undefined,
  label: item.strong ? <span style={{ fontWeight: 700 }}>{item.label}</span> : item.label,
  children: item.children ? toMenuItems(item.children, depth + 1) : undefined,
}));

const toCollapsedMenuItems = (items: SideNavigationItem[]): NonNullable<MenuProps['items']> =>
  items.map((item) => ({
    key: item.path,
    icon: item.icon ? renderMenuIcon(item.icon) : undefined,
    label: item.strong ? <span style={{ fontWeight: 700 }}>{item.label}</span> : item.label,
  }));

export function SideNavigation({
  collapsed,
  currentPath,
  items,
  onNavigate,
  defaultOpenKeys = [],
}: SideNavigationProps) {
  const { token } = theme.useToken();

  const menuItems = useMemo(() => toMenuItems(items), [items]);
  const collapsedMenuItems = useMemo(() => toCollapsedMenuItems(items), [items]);

  const routeOpenKeys = useMemo(
    () => items
      .filter((item) => item.children?.length && isPathMatch(currentPath, item.path))
      .map((item) => item.path),
    [currentPath, items]
  );

  const [openKeys, setOpenKeys] = useState<string[]>(() => Array.from(
    new Set([...defaultOpenKeys, ...routeOpenKeys])
  ));

  const selectedKey = useMemo(() => {
    const matches = flattenItems(items)
      .filter((item) => isPathMatch(currentPath, item.path))
      .sort((left, right) => right.path.length - left.path.length);
    return matches[0]?.path;
  }, [currentPath, items]);

  const activeRootKey = useMemo(() => {
    if (!selectedKey) return undefined;
    return items.find((item) => item.path === selectedKey || isPathMatch(selectedKey, item.path))?.path;
  }, [items, selectedKey]);

  useEffect(() => {
    setOpenKeys((current) => Array.from(new Set([...current, ...routeOpenKeys])));
  }, [routeOpenKeys]);

  return (
    <Menu
      mode="inline"
      inlineCollapsed={collapsed}
      selectedKeys={collapsed ? (activeRootKey ? [activeRootKey] : []) : (selectedKey ? [selectedKey] : [])}
      openKeys={collapsed ? [] : openKeys}
      onOpenChange={collapsed ? undefined : (keys) => setOpenKeys(keys as string[])}
      items={collapsed ? collapsedMenuItems : menuItems}
      onClick={({ key }) => onNavigate(key)}
      inlineIndent={18}
      style={{
        borderRight: 'none',
        padding: '16px 10px',
        background: 'transparent',
        color: token.colorText,
        width: '100%',
        pointerEvents: collapsed ? 'none' : 'auto',
      }}
    />
  );
}
