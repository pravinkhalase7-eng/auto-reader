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

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) await parseError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
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
