"use client";

import { Phone } from "lucide-react";
import { Card } from "@/components/ui/card";
import { CallStatusBadge } from "@/components/pavi/CallStatusBadge";
import type { Reminder } from "@/types/pavi";

export function ReminderCard({ reminder }: { reminder: Reminder }) {
  return (
    <Card className="space-y-1.5 rounded-2xl p-3.5 shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-teal-950">{reminder.title}</p>
          <p className="text-sm text-teal-800/70">{reminder.when_label}</p>
        </div>
        <CallStatusBadge status={reminder.status} />
      </div>
      {reminder.phone_call_enabled && (
        <p className="flex items-center gap-1.5 text-sm text-teal-800/80">
          <Phone className="h-3.5 w-3.5" /> Voice reminder enabled
        </p>
      )}
      {reminder.last_error && <p className="text-sm text-rose-700">{reminder.last_error}</p>}
    </Card>
  );
}
