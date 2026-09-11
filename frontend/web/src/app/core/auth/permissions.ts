// src/app/core/auth/permissions.ts
import { Action, AppRole, PermissionRule, UserPermissions } from './types';

const VIEWER_PERMISSIONS: UserPermissions = [
  { resource: 'contract', action: ['read'] },
  { resource: 'marketdata', action: ['read'] },
  { resource: 'calculation', action: ['history'] },
  { resource: 'report', action: ['view'] },
  { resource: 'dashboard', action: ['view'] },
  { resource: 'gl-balance', action: ['read', 'create', 'edit', 'run', 'export'] },
  { resource: 'gl-tree', action: ['read', 'create', 'edit'] },
];

const ADMIN_PERMISSIONS: UserPermissions = [
  { resource: '*', action: '*' },
];

export function normalizeRoles(roles?: readonly string[] | null): AppRole[] {
  const normalizedRoles = (roles || []).filter((role): role is AppRole => role === 'admin' || role === 'viewer');

  return normalizedRoles.length > 0 ? Array.from(new Set(normalizedRoles)) : ['viewer'];
}

export function getPermissionsForRoles(roles?: readonly string[] | null): UserPermissions {
  const normalizedRoles = normalizeRoles(roles);

  if (normalizedRoles.includes('admin')) {
    return ADMIN_PERMISSIONS;
  }

  return VIEWER_PERMISSIONS;
}

export function checkPermission(
  userRules: UserPermissions | undefined,
  resource: string,
  requiredAction: Action,
  resourceAttributes?: Partial<PermissionRule['constraints']>
): boolean {
  if (!userRules || userRules.length === 0) return false;

  return userRules.some((rule) => {
    if (rule.resource !== resource && rule.resource !== '*') return false;

    const actions = Array.isArray(rule.action) ? rule.action : [rule.action];
    if (!actions.includes(requiredAction) && !actions.includes('*' as Action)) return false;

    if (!rule.constraints) return true;

    const attrs = resourceAttributes || {};
    const constraints = rule.constraints;

    if (constraints.categories && attrs.categories) {
      const categoryArray = Array.isArray(attrs.categories) ? attrs.categories : [attrs.categories];
      if (!categoryArray.some(cat => constraints.categories!.includes(cat))) return false;
    }
    if (constraints.markets && attrs.markets) {
      const marketArray = Array.isArray(attrs.markets) ? attrs.markets : [attrs.markets];
      if (!marketArray.some(m => constraints.markets!.includes(m))) return false;
    }
    if (constraints.regions && attrs.regions) {
      const regionArray = Array.isArray(attrs.regions) ? attrs.regions : [attrs.regions];
      if (!regionArray.some(r => constraints.regions!.includes(r))) return false;
    }
    if (constraints.counterparties && attrs.counterparties) {
      const cpArray = Array.isArray(attrs.counterparties) ? attrs.counterparties : [attrs.counterparties];
      if (!cpArray.some(cp => constraints.counterparties!.includes(cp))) return false;
    }

    return true;
  });
}

export function canPerform(
  userRules: UserPermissions | undefined,
  resource: string,
  action: Action,
  attrs?: Partial<PermissionRule['constraints']>
): boolean {
  return checkPermission(userRules, resource, action, attrs);
}

// SSO: Временная моковая функция. Будет заменена на данные из JWT/API
export function getMockPermissions(username: string): UserPermissions {
  if (username === 'admin') return getPermissionsForRoles(['admin']);

  if (username === 'gas_trader') {
    return [
      { resource: 'contract', action: ['read', 'create', 'export'] },
      { resource: 'contract', action: ['edit', 'delete'], constraints: { categories: ['gas'] } },
      { resource: 'marketdata', action: ['read'] },
      { resource: 'calculation', action: ['run', 'history', 'download'] },
      { resource: 'report', action: ['view'] },
      { resource: 'dashboard', action: ['view'] },
    ];
  }

  if (username === 'oil_trader') {
    return [
      { resource: 'contract', action: ['read', 'create', 'export'] },
      { resource: 'contract', action: ['edit', 'delete'], constraints: { categories: ['oil'] } },
      { resource: 'marketdata', action: ['read'] },
      { resource: 'calculation', action: ['run', 'history', 'download'] },
      { resource: 'report', action: ['view'] },
      { resource: 'dashboard', action: ['view'] },
    ];
  }

  return getPermissionsForRoles(['viewer']);
}
