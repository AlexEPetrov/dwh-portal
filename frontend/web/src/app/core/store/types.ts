// src/app/core/store/types.ts
import { AuthState } from './slices/auth.slice';
import { CoreState } from './slices/core.slice';
import { PermissionsState } from './slices/permissions.slice';

/** Feature slices extend this interface by declaration merging before registration. */
export interface ModuleState { }

export interface RootState extends CoreState, AuthState, PermissionsState, ModuleState { }
