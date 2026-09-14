import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Prefer same-origin `/api/v1` (Next rewrite → API) so login works without CORS. */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window === "undefined"
    ? process.env.API_PROXY_TARGET
      ? `${process.env.API_PROXY_TARGET.replace(/\/$/, "")}/api/v1`
      : "http://127.0.0.1:8000/api/v1"
    : "/api/v1");

export function formatPercent(n: number) {
  return `${Math.round(n)}%`;
}
