// src/app/core/api/client.ts
import axios from 'axios';
import { setStoreGetter, setupInterceptors } from './interceptors';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Функция инициализации, вызывается после создания стора
export function initApiClient(storeGetter: () => any) {
  setStoreGetter(storeGetter);
  setupInterceptors(apiClient);
}
