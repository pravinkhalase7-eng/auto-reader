"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth-store";

export default function SettingsPage() {
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);
  if (!token) return null;

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold text-teal-950">Settings</h1>
      <Card className="mt-6 max-w-lg space-y-3">
        <p className="font-semibold text-teal-950">UI language</p>
        <p className="text-sm text-teal-900/70">
          English (lesson language stays independent — Hindi/Marathi lessons still quiz in those languages).
        </p>
        <p className="font-semibold text-teal-950">Reading speed default</p>
        <p className="text-sm text-teal-900/70">Slow — comfortable for children (change anytime in the reader).</p>
      </Card>
    </AppShell>
  );
}
