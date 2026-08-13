"use client";

import { Check, Phone } from "lucide-react";
import type { PaviConfirmation } from "@/types/pavi";

export function PaviConfirmationCard({ confirmation }: { confirmation: PaviConfirmation }) {
  return (
    <div className="ml-10 max-w-sm rounded-2xl border border-teal-900/8 bg-white p-4 shadow-[0_8px_24px_-16px_rgba(15,80,70,0.4)]">
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-teal-700">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 text-white">
          <Check className="h-3 w-3" />
        </span>
        {confirmation.kind === "appointment" ? "Appointment added" : "Reminder created"}
      </p>
      <p className="mt-2 font-display text-lg font-semibold text-teal-950">{confirmation.title}</p>
      <p className="text-sm text-teal-800/70">{confirmation.when_label}</p>
      {confirmation.phone_call_enabled && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-teal-800/80">
          <Phone className="h-3.5 w-3.5" /> Phone reminder enabled
        </p>
      )}
      {confirmation.extra && <p className="mt-1 text-sm text-teal-800/60">{confirmation.extra}</p>}
    </div>
  );
}
