import { Interceptors, OpenAPI, type OpenAPIConfig } from '@shared/api/generated/core/OpenAPI';
import axios from 'axios';
import { isProtectedPortalResponse } from './interceptors';

export interface ServiceClientOptions {
  baseUrl: string;
  /** Deliberately opt in per service; secondary services inherit no Portal credentials. */
  credentials?: RequestCredentials;
  getApiKey?: () => string | null;
  onUnauthorized?: () => void;
}

/** Independent generated-client configuration; never change a shared BASE per request. */
export function createServiceConfig(options: ServiceClientOptions): OpenAPIConfig {
  const { baseUrl, credentials = 'omit', getApiKey, onUnauthorized } = options;
  const config: OpenAPIConfig = {
    BASE: baseUrl,
    VERSION: OpenAPI.VERSION,
    WITH_CREDENTIALS: true,
    CREDENTIALS: credentials,
    interceptors: {
      request: new Interceptors<RequestInit>(),
      response: new Interceptors<Response>(),
    },
  };
  if (getApiKey) {
    // Apply after generated operation headers: the session operation declares an
    // optional key whose undefined value otherwise masks config-level HEADERS.
    config.interceptors.request.use((request) => {
      const headers = new Headers(request.headers);
      const key = getApiKey();
      if (key && !headers.has('x-api-key')) headers.set('x-api-key', key);
      return { ...request, headers };
    });
  }
  if (onUnauthorized) {
    config.interceptors.response.use((response) => {
      if (response.status === 401) onUnauthorized();
      return response;
    });
  }
  return Object.freeze(config);
}

const portalBase = import.meta.env.VITE_API_BASE_URL || '';
// Existing host configuration uses an API root (for example /api), whereas
// generated operations already include /api. Preserve any deployment prefix,
// stripping only the final API segment and trailing slashes for generated calls.
const portalGeneratedBase = portalBase.replace(/\/+$/, '').replace(/\/api$/, '');
const getPortalApiKey = () => localStorage.getItem('x_api_key');
let expirePortalSession: (() => void) | undefined;
const handlePortalUnauthorized = (url: string) => {
  if (!isProtectedPortalResponse(url, portalBase)) return;
  expirePortalSession?.();
  if (window.location.pathname !== '/login') window.location.href = '/login';
};

// Generated Portal services use this config. Configure once at module load,
// before any session bootstrap; other service configs never mutate this object.
Object.assign(OpenAPI, createServiceConfig({
  baseUrl: portalGeneratedBase,
  credentials: 'include',
  getApiKey: getPortalApiKey,
}));
OpenAPI.interceptors.response.use((response) => {
  if (response.status === 401) handlePortalUnauthorized(response.url);
  return response;
});

/** Legacy blob utility only; API operations must continue using generated services. */
export const apiClient = axios.create({
  baseURL: portalBase,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const base = new URL(portalBase || '/', window.location.origin);
  const target = new URL(apiClient.getUri(config), window.location.origin);
  if (target.origin !== base.origin) throw new Error('Portal client cannot send credentials to another service origin');
  const key = getPortalApiKey();
  if (key) config.headers.set('x-api-key', key);
  return config;
});
apiClient.interceptors.response.use((response) => response, (error: unknown) => {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    handlePortalUnauthorized(error.response.request?.responseURL || apiClient.getUri(error.config));
  }
  return Promise.reject(error);
});

export function initApiClient(onUnauthorized: () => void): void {
  expirePortalSession = onUnauthorized;
}
