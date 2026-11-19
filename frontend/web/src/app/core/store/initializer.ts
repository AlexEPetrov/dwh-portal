// src/app/core/store/initializer.ts
import { pluginRegistry } from '@asset-management/app-shell/plugin';
import { create, StoreApi, UseBoundStore } from 'zustand';
import { devtools } from 'zustand/middleware';
import { initApiClient } from '../api';
import { clearPrivateQueryData } from '../queryClient';
import { getRegisteredZustandSlices } from './pluginContributions';
import { createAuthSlice, createCoreSlice, createPermissionsSlice } from './slices';
import { RootState } from './types';

// Жесткая типизация синглтона стора вместо any
let store: UseBoundStore<StoreApi<RootState>> | null = null;

export function initializeStore(): UseBoundStore<StoreApi<RootState>> {
  if (!store) {
    const moduleSlices = getRegisteredZustandSlices(pluginRegistry);

    store = create<RootState>()(devtools((...a) => {
      const result: Record<string, unknown> = {};
      const owners = new Map<string, string>();
      const merge = (owner: string, slice: object) => {
        for (const [key, value] of Object.entries(slice)) {
          if (owners.has(key)) {
            throw new Error(`Duplicate flat store key "${key}" in ${owner}; already owned by ${owners.get(key)}`);
          }
          owners.set(key, owner);
          Object.defineProperty(result, key, { value, writable: true, enumerable: true, configurable: true });
        }
      };
      merge('core', createCoreSlice(...a));
      merge('auth', createAuthSlice(...a));
      merge('permissions', createPermissionsSlice(...a));
      for (const [name, createSlice] of Object.entries(moduleSlices)) merge(name, createSlice(...a));
      // Dynamic registration is checked at runtime; public selectors use declared RootState.
      return result as unknown as RootState;
    }));

    // No obsolete selectedContractSlug persistence: that key has no slice or consumers.
    // Leave existing browser storage untouched rather than hydrating unknown legacy keys.
    store.subscribe((state, previous) => {
      if (state.user?.id !== previous.user?.id ||
        state.isAuthenticated !== previous.isAuthenticated ||
        state.authType !== previous.authType ||
        JSON.stringify(state.permissions) !== JSON.stringify(previous.permissions)) {
        clearPrivateQueryData();
      }
    });
    const currentStore = store;
    initApiClient(() => {
      clearPrivateQueryData();
      currentStore.setState({ user: null, permissions: [], authType: null, isAuthenticated: false, isLoading: false });
    });
  }
  return store;
}

/**
 * Хук для использования в React-компонентах. Оснащен полной поддержкой TypeScript.
 */
export function useStore<T>(selector: (state: RootState) => T): T;
export function useStore(): RootState;
export function useStore<T>(selector?: (state: RootState) => T): T | RootState {
  const currentStore = store || initializeStore();
  return selector ? currentStore(selector) : currentStore();
}

// Статические методы для использования вне React-компонентов (сервисы, утилиты)
useStore.getState = () => (store || initializeStore()).getState();
useStore.setState = (state: Partial<RootState> | ((state: RootState) => Partial<RootState>)) =>
  (store || initializeStore()).setState(state);
useStore.subscribe = (listener: (state: RootState, prevState: RootState) => void) =>
  (store || initializeStore()).subscribe(listener);

// Функция сброса стора для использования в тестах (beforeEach) или при logout
export const resetStoreForTesting = () => {
  store = null;
};

export const getUseStore = useStore;
export default useStore;
