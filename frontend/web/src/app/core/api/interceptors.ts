/** Login/session failures belong to their caller, not a global logout loop. */
export function isProtectedPortalResponse(url: string, portalBase: string): boolean {
  if (!url) return false;
  const base = new URL(portalBase || '/', window.location.origin);
  const response = new URL(url, base);
  return response.origin === base.origin && !/\/api\/auth\/(login|logout|session)\/?$/.test(response.pathname);
}
