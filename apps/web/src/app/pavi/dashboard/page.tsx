"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UpcomingSchedule } from "@/components/pavi/UpcomingSchedule";
import { CallStatusBadge } from "@/components/pavi/CallStatusBadge";
import { getConversations, getPhoneCallHistory, getPaviStats, getUpcomingSchedule } from "@/lib/pavi-api";
import { useRequireAuth } from "@/lib/use-require-auth";

export default function PaviDashboardPage() {
  const { token, ready } = useRequireAuth();
  const stats = useQuery({ queryKey: ["pavi-stats"], queryFn: getPaviStats, enabled: !!token });
  const schedule = useQuery({ queryKey: ["pavi-schedule"], queryFn: getUpcomingSchedule, enabled: !!token });
  const calls = useQuery({ queryKey: ["pavi-calls"], queryFn: getPhoneCallHistory, enabled: !!token });
  const convos = useQuery({ queryKey: ["pavi-conversations"], queryFn: getConversations, enabled: !!token });
  if (!ready) return null;

  const s = stats.data;
  return (
    <AppShell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-teal-950">Pavi dashboard</h1>
          <p className="mt-1 text-teal-900/70">Reminders, appointments, and recent calls.</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/pavi">Open assistant</Link>
          </Button>
          <Button asChild>
            <Link href="/pavi/reminders/new">New reminder</Link>
          </Button>
        </div>
      </div>

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          ["Total reminders", s?.total_reminders ?? 0],
          ["Pending", s?.pending_reminders ?? 0],
          ["Completed", s?.completed_reminders ?? 0],
          ["Failed", s?.failed_reminders ?? 0],
          ["Calls made", s?.calls_made ?? 0],
          ["Calls answered", s?.calls_answered ?? 0],
        ].map(([label, value]) => (
          <Card key={String(label)}>
            <p className="text-xs font-semibold uppercase tracking-wide text-teal-900/50">{label}</p>
            <p className="font-display text-2xl font-bold text-teal-950">{stats.isLoading ? "—" : value}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <h2 className="font-display mb-4 text-xl font-semibold text-teal-950">Schedule</h2>
          <UpcomingSchedule
            today={schedule.data?.today || []}
            tomorrow={schedule.data?.tomorrow || []}
            later={schedule.data?.later || []}
          />
        </Card>
        <div className="space-y-8">
          <Card>
            <h2 className="font-display mb-4 text-xl font-semibold text-teal-950">Recent calls</h2>
            <ul className="space-y-3">
              {(calls.data || []).slice(0, 6).map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-teal-900">{c.phone_number_masked || "Call"} · {c.provider}</span>
                  <CallStatusBadge status={c.status} />
                </li>
              ))}
              {!calls.data?.length && <p className="text-sm text-teal-800/60">No calls yet.</p>}
            </ul>
          </Card>
          <Card>
            <h2 className="font-display mb-4 text-xl font-semibold text-teal-950">Recent conversations</h2>
            <ul className="space-y-2 text-sm text-teal-800">
              {(convos.data || []).slice(0, 6).map((c) => (
                <li key={c.id}>{c.title}</li>
              ))}
              {!convos.data?.length && <p className="text-teal-800/60">No conversations yet.</p>}
            </ul>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
