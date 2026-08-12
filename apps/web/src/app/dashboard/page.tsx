"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookPlus, Flame, Timer, Trophy } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { LessonCardView } from "@/components/lesson-card";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Dashboard } from "@/types";
import { useAuthStore } from "@/store/auth-store";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function DashboardPage() {
  const token = useAuthStore((s) => s.token);
  const router = useRouter();

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/dashboard"),
    enabled: !!token,
  });

  if (!token) return null;

  return (
    <AppShell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-teal-950 md:text-4xl">My Learning</h1>
          <p className="mt-2 max-w-2xl text-teal-900/75">{data?.greeting || "Loading your classroom..."}</p>
        </div>
        <Button asChild size="lg">
          <Link href="/upload">
            <BookPlus className="h-4 w-4" /> New story
          </Link>
        </Button>
      </div>

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Flame, label: "Streak", value: `${data?.streak ?? 0} days` },
          { icon: Trophy, label: "Average score", value: `${Math.round(data?.average_score ?? 0)}%` },
          { icon: Timer, label: "Reading time", value: `${data?.reading_time_minutes ?? 0} min` },
          { icon: Trophy, label: "Completed", value: `${data?.completed_count ?? 0}` },
        ].map((s) => (
          <Card key={s.label} className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
              <s.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-teal-900/50">{s.label}</p>
              <p className="font-display text-xl font-bold text-teal-950">{isLoading ? "—" : s.value}</p>
            </div>
          </Card>
        ))}
      </div>

      {data?.subjects?.length ? (
        <section className="mb-10">
          <h2 className="font-display mb-4 text-2xl font-semibold text-teal-950">Subjects</h2>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            {data.subjects.map((s) => (
              <Link
                key={s.name}
                href={`/lessons?subject=${encodeURIComponent(s.name)}`}
                className="block rounded-[1.5rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
              >
                <Card className="h-full bg-teal-50/60 transition hover:-translate-y-0.5 hover:shadow-lg">
                  <p className="font-semibold text-teal-950">{s.name}</p>
                  <p className="text-sm text-teal-800/70">
                    {s.count} lessons · {Math.round(s.avg_progress)}%
                  </p>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {data?.continue_learning?.length ? (
        <section className="mb-10">
          <h2 className="font-display mb-4 text-2xl font-semibold text-teal-950">Continue learning</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {data.continue_learning.map((l) => (
              <LessonCardView key={l.id} lesson={l} />
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-2xl font-semibold text-teal-950">Recent lessons</h2>
          <Link href="/lessons" className="text-sm font-semibold text-teal-800 underline">
            View all
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(data?.recent_lessons || []).map((l) => (
            <LessonCardView key={l.id} lesson={l} />
          ))}
        </div>
      </section>
    </AppShell>
  );
}
