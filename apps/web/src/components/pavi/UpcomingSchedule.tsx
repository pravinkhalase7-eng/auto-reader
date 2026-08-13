"use client";

import { Phone } from "lucide-react";
import type { ScheduleItem } from "@/types/pavi";

function Group({ label, items }: { label: string; items: ScheduleItem[] }) {
  if (!items.length) return null;
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-teal-900/50">{label}</h3>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={`${item.kind}-${item.id}`} className="rounded-2xl border border-teal-900/10 bg-white/80 px-4 py-3">
            <p className="text-sm font-semibold text-teal-950">
              {item.when_label} · {item.title}
            </p>
            {item.location && <p className="text-sm text-teal-800/70">{item.location}</p>}
            {item.phone_call_enabled && (
              <p className="mt-1 flex items-center gap-1 text-xs text-teal-800/70">
                <Phone className="h-3 w-3" /> Voice reminder
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function UpcomingSchedule({
  today,
  tomorrow,
  later,
}: {
  today: ScheduleItem[];
  tomorrow: ScheduleItem[];
  later: ScheduleItem[];
}) {
  if (!today.length && !tomorrow.length && !later.length) {
    return <p className="text-sm text-teal-800/70">No upcoming reminders yet.</p>;
  }
  return (
    <div className="space-y-6">
      <Group label="Today" items={today} />
      <Group label="Tomorrow" items={tomorrow} />
      <Group label="Later" items={later} />
    </div>
  );
}
