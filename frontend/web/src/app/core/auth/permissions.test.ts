import { describe, expect, it } from 'vitest';
import { canPerform, getPermissionsForRoles } from './permissions';

describe('viewer screen permissions', () => {
    it('keeps existing viewer access but denies restricted screens', () => {
        const permissions = getPermissionsForRoles(['viewer']);

        expect(canPerform(permissions, 'marketdata', 'read')).toBe(true);
        expect(canPerform(permissions, 'contracts-screen', 'view')).toBe(false);
        expect(canPerform(permissions, 'factor-analysis-screen', 'view')).toBe(false);
        expect(canPerform(permissions, 'scenario-analysis-screen', 'view')).toBe(false);
        expect(canPerform(permissions, 'admin', 'edit')).toBe(false);
    });

    it('allows restricted screens for admins', () => {
        const permissions = getPermissionsForRoles(['admin']);

        expect(canPerform(permissions, 'contracts-screen', 'view')).toBe(true);
        expect(canPerform(permissions, 'factor-analysis-screen', 'view')).toBe(true);
        expect(canPerform(permissions, 'scenario-analysis-screen', 'view')).toBe(true);
        expect(canPerform(permissions, 'admin', 'edit')).toBe(true);
    });
});
