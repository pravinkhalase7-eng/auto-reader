"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { User } from "@/types";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const res = await api<{ user: User; access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: fd.get("email"),
          password: fd.get("password"),
          full_name: fd.get("full_name"),
          class_level: Number(fd.get("class_level") || 3),
        }),
      });
      setAuth(res.user, res.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not register");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <Card>
        <h1 className="font-display text-3xl font-bold text-teal-950">Join AI Teacher</h1>
        <p className="mt-2 text-sm text-teal-900/70">Create your student account and start learning.</p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block text-sm font-semibold text-teal-900">
            Full name
            <input name="full_name" required className="mt-1 w-full rounded-2xl border border-teal-900/15 px-4 py-3" />
          </label>
          <label className="block text-sm font-semibold text-teal-900">
            Email
            <input name="email" type="email" required className="mt-1 w-full rounded-2xl border border-teal-900/15 px-4 py-3" />
          </label>
          <label className="block text-sm font-semibold text-teal-900">
            Password
            <input name="password" type="password" minLength={6} required className="mt-1 w-full rounded-2xl border border-teal-900/15 px-4 py-3" />
          </label>
          <label className="block text-sm font-semibold text-teal-900">
            Class
            <select name="class_level" defaultValue={3} className="mt-1 w-full rounded-2xl border border-teal-900/15 px-4 py-3">
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  Class {n}
                </option>
              ))}
            </select>
          </label>
          {error ? <p className="text-sm text-rose-700">{error}</p> : null}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Creating..." : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-teal-900/70">
          Already learning? <Link className="font-semibold text-teal-800 underline" href="/login">Sign in</Link>
        </p>
      </Card>
    </div>
  );
}
