"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth-store";

export default function ProfilePage() {
  const { user, token } = useAuthStore();
  const router = useRouter();
  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);
  if (!token) return null;

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold text-teal-950">Profile</h1>
      <Card className="mt-6 max-w-lg">
        <p className="text-sm text-teal-900/60">Student</p>
        <p className="font-display text-2xl font-semibold text-teal-950">{user?.full_name}</p>
        <p className="mt-2 text-teal-900/80">{user?.email}</p>
        <p className="mt-4 text-sm text-teal-900/70">Class {user?.profile?.class_level ?? "—"}</p>
        <p className="text-sm text-teal-900/70">Streak: {user?.profile?.learning_streak ?? 0} days</p>
      </Card>
    </AppShell>
  );
}
