// src/app/core/api/interceptors.ts
import { AxiosInstance } from 'axios';

// Ленивый импорт useStore, чтобы избежать циклической зависимости
let storeGetter: (() => any) | null = null;

export function setStoreGetter(getter: () => any) {
  storeGetter = getter;
}

export function setupInterceptors(instance: AxiosInstance) {
  instance.interceptors.request.use((config) => {
    const apiKey = localStorage.getItem('x_api_key');
    if (apiKey) {
      (config.headers as Record<string, string>)['x-api-key'] = apiKey;
    }
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        storeGetter?.()?.logout();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
      return Promise.reject(error);
    }
  );
}
