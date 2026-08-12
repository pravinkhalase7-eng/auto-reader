"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { LessonCardView } from "@/components/lesson-card";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import type { LessonCard } from "@/types";

export default function LessonsPage() {
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data = [], isLoading } = useQuery({
    queryKey: ["lessons"],
    queryFn: () => api<LessonCard[]>("/lessons"),
    enabled: !!token,
  });

  if (!token) return null;

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold text-teal-950">Lesson Library</h1>
      <p className="mt-2 text-teal-900/70">All your lessons and demo stories in one place.</p>
      {isLoading ? <p className="mt-8">Loading lessons...</p> : null}
      <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data.map((l) => (
          <LessonCardView key={l.id} lesson={l} />
        ))}
      </div>
    </AppShell>
  );
}
