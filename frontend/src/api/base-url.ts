const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = configuredApiBaseUrl || "/api";

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (!configuredApiBaseUrl) return path;

  const base = configuredApiBaseUrl.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/api/")
    ? path.slice("/api".length)
    : path.startsWith("/api")
      ? path.slice("/api".length)
      : path;
  const normalizedPath = cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`;

  return `${base}${normalizedPath}`;
}
