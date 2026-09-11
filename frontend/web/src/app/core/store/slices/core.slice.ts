// src/app/core/store/slices/core.slice.ts
import { StateCreator } from 'zustand';

export interface CoreState {
  theme: 'light' | 'dark';
  notifications: Array<{ id: string; message: string; type: 'info' | 'success' | 'error' }>;
  addNotification: (message: string, type?: 'info' | 'success' | 'error') => void;
  removeNotification: (id: string) => void;
}

export const createCoreSlice: StateCreator<CoreState> = (set) => ({
  theme: 'light',
  notifications: [],
  addNotification: (message, type = 'info') =>
    set((state) => ({
      notifications: [...state.notifications, { id: Date.now().toString(), message, type }],
    })),
  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
});
