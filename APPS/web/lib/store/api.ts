/**
 * Axios API client.
 * - Injects JWT access token on every request.
 * - On 401: attempts silent refresh, then retries once.
 * - On second 401: clears auth state and redirects to /login.
 */
import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosError,
  InternalAxiosRequestConfig,
} from "axios";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Token storage — in-memory for security; refresh token is in HttpOnly cookie. */
let accessToken: string | null = null;
let isRefreshing = false;
let refreshQueue: Array<(token: string | null) => void> = [];

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// ── Axios instance ────────────────────────────────────────────────────────────

export const api: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 30_000,
  withCredentials: true, // send HttpOnly refresh cookie
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Request interceptor: inject Bearer token ──────────────────────────────────

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  // Inject active workspace ID if stored
  const workspaceId =
    typeof window !== "undefined"
      ? localStorage.getItem("catai_workspace_id")
      : null;
  if (workspaceId) {
    config.headers["X-Workspace-Id"] = workspaceId;
  }

  return config;
});

// ── Response interceptor: silent token refresh on 401 ────────────────────────

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    // Don't retry refresh endpoint itself
    if (original.url?.includes("/auth/refresh")) {
      clearAuthAndRedirect();
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // Queue requests while refresh is in progress
      return new Promise((resolve, reject) => {
        refreshQueue.push((newToken) => {
          if (newToken) {
            original._retry = true;
            if (original.headers) {
              original.headers.Authorization = `Bearer ${newToken}`;
            }
            resolve(api(original));
          } else {
            reject(error);
          }
        });
      });
    }

    original._retry = true;
    isRefreshing = true;

    try {
      const response = await api.post<{ access_token: string }>("/auth/refresh");
      const newToken = response.data.access_token;
      setAccessToken(newToken);

      // Drain the queue
      refreshQueue.forEach((cb) => cb(newToken));
      refreshQueue = [];

      if (original.headers) {
        original.headers.Authorization = `Bearer ${newToken}`;
      }
      return api(original);
    } catch {
      refreshQueue.forEach((cb) => cb(null));
      refreshQueue = [];
      clearAuthAndRedirect();
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  }
);

function clearAuthAndRedirect() {
  setAccessToken(null);
  if (typeof window !== "undefined") {
    localStorage.removeItem("catai_workspace_id");
    window.location.href = "/login";
  }
}

export default api;