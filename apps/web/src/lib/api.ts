import { API_URL } from "@/lib/utils";

const TOKEN_KEY = "ai_teacher_token";
const AUTH_PERSIST_KEY = "ai-teacher-auth";

function tokenFromPersist(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_PERSIST_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { state?: { token?: unknown } };
    const token = parsed?.state?.token;
    return typeof token === "string" && token ? token : null;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const direct = localStorage.getItem(TOKEN_KEY);
  if (direct) return direct;
  const persisted = tokenFromPersist();
  if (persisted) {
    localStorage.setItem(TOKEN_KEY, persisted);
    return persisted;
  }
  return null;
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  code?: string;
  constructor(message: string, code?: string) {
    super(message);
    this.code = code;
  }
}

async function parseError(res: Response) {
  try {
    const data = await res.json();
    const detail = data.detail;
    const code = data.code || (res.status === 401 ? "UNAUTHORIZED" : undefined);
    if (typeof detail === "string") throw new ApiError(detail, code);
    if (detail?.detail) throw new ApiError(detail.detail, detail.code || code);
    throw new ApiError(res.status === 401 ? "Please sign in to continue." : "Something went wrong. Let's try again.", code);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(res.status === 401 ? "Please sign in to continue." : "Something went wrong. Let's try again.", res.status === 401 ? "UNAUTHORIZED" : undefined);
  }
}

function apiBases(): string[] {
  // Prefer same-origin proxy; fall back to local API ports if an old UI build is open.
  const preferred = (API_URL || "/api/v1").replace(/\/$/, "");
  const extras = ["http://127.0.0.1:8001/api/v1", "http://127.0.0.1:8000/api/v1"];
  return [preferred, ...extras.filter((b) => b !== preferred)];
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let lastErr: unknown;
  for (const base of apiBases()) {
    try {
      const res = await fetch(`${base}${path}`, { ...options, headers });
      // Same-origin proxy miss on old Next servers returns HTML 404 — try next base.
      if (res.status === 404 && base.startsWith("/")) {
        lastErr = new ApiError("API proxy missing on this port.");
        continue;
      }
      if (!res.ok) await parseError(res);
      if (res.status === 204) return undefined as T;
      return res.json() as Promise<T>;
    } catch (err) {
      lastErr = err;
      // Network/CORS "Failed to fetch" → try the next base URL.
      if (err instanceof TypeError || (err instanceof Error && /failed to fetch/i.test(err.message))) {
        continue;
      }
      throw err;
    }
  }
  throw lastErr instanceof Error
    ? new ApiError(
        "Cannot reach the API. Use http://127.0.0.1:3003/login (demo@example.com / demo1234).",
      )
    : new ApiError("Cannot reach the API. Please retry.");
}

export async function apiAudio(path: string, body: unknown): Promise<Blob> {
  const token = getToken();
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) await parseError(res);
  return res.blob();
}
