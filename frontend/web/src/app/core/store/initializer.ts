// src/app/core/store/initializer.ts
import { create, StoreApi, UseBoundStore } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { initApiClient } from '../api';
import { pluginRegistry } from '@asset-management/app-shell/plugin';
import { createAuthSlice, createCoreSlice, createPermissionsSlice } from './slices';
import { getRegisteredZustandSlices } from './pluginContributions';
import { RootState } from './types';

// Жесткая типизация синглтона стора вместо any
let store: UseBoundStore<StoreApi<RootState>> | null = null;

export function initializeStore(): UseBoundStore<StoreApi<RootState>> {
  if (!store) {
    const moduleSlices = getRegisteredZustandSlices(pluginRegistry);

    store = create<RootState>()(
      persist(
        devtools((...a) => {
          // Safe-сборка динамических слайсов для предотвращения коллизий
          const dynamicSlices = Object.entries(moduleSlices).reduce((acc, [, sliceFn]) => {
            // Если слайс написан как фабрика, передаем ему все аргументы Zustand (...a)
            return { ...acc, ...sliceFn(...a) };
          }, {});

          return {
            ...createCoreSlice(...a),
            ...createAuthSlice(...a),
            ...createPermissionsSlice(...a),
            ...dynamicSlices,
          };
        }),
        {
          name: 'atrm-store',
          partialize: (state) => ({
            selectedContractSlug: state.selectedContractSlug,
          }),
        }
      )
    );

    // Инициализация API с ленивым получением актуального стейта
    initApiClient(() => (store as UseBoundStore<StoreApi<RootState>>).getState());
  }
  return store;
}

/**
 * Хук для использования в React-компонентах. Оснащен полной поддержкой TypeScript.
 */
export function useStore<T>(selector: (state: RootState) => T): T;
export function useStore(): RootState;
export function useStore(selector?: any) {
  const currentStore = store || initializeStore();
  return selector ? currentStore(selector) : currentStore();
}

// Статические методы для использования вне React-компонентов (сервисы, утилиты)
useStore.getState = () => (store || initializeStore()).getState();
useStore.setState = (state: Partial<RootState> | ((state: RootState) => Partial<RootState>)) =>
  (store || initializeStore()).setState(state as any);
useStore.subscribe = (listener: (state: RootState, prevState: RootState) => void) =>
  (store || initializeStore()).subscribe(listener);

// Функция сброса стора для использования в тестах (beforeEach) или при logout
export const resetStoreForTesting = () => {
  store = null;
};

export const getUseStore = useStore;
export default useStore;
