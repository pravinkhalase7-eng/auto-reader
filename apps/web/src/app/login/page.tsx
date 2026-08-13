"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { useAuthHydrated } from "@/lib/use-require-auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { User } from "@/types";

function safeNext(raw: string | null) {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";
  return raw;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const setAuth = useAuthStore((s) => s.setAuth);
  const token = useAuthStore((s) => s.token);
  const hydrated = useAuthHydrated();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (hydrated && token) router.replace(next);
  }, [hydrated, token, next, router]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const res = await api<{ user: User; access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: fd.get("email"),
          password: fd.get("password"),
        }),
      });
      setAuth(res.user, res.access_token);
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <Card>
        <h1 className="font-display text-3xl font-bold text-teal-950">Welcome back</h1>
        <p className="mt-2 text-sm text-teal-900/70">
          Demo account: <code>demo@example.com</code> / <code>demo1234</code>
        </p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block text-sm font-semibold text-teal-900">
            Email
            <input
              name="email"
              type="email"
              required
              defaultValue="demo@example.com"
              className="mt-1 w-full rounded-2xl border border-teal-900/15 bg-white px-4 py-3"
            />
          </label>
          <label className="block text-sm font-semibold text-teal-900">
            Password
            <input
              name="password"
              type="password"
              required
              defaultValue="demo1234"
              className="mt-1 w-full rounded-2xl border border-teal-900/15 bg-white px-4 py-3"
            />
          </label>
          {error ? <p className="text-sm text-rose-700">{error}</p> : null}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-teal-900/70">
          New here? <Link className="font-semibold text-teal-800 underline" href="/register">Create an account</Link>
        </p>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
