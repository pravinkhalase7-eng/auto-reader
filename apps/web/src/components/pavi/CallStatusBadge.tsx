"use client";

import { Phone } from "lucide-react";
import { cn } from "@/lib/utils";
import { isFailedStatus, statusLabel } from "@/lib/pavi-format";

export function CallStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold",
        isFailedStatus(status) ? "bg-rose-50 text-rose-800" : status === "completed" ? "bg-emerald-50 text-emerald-800" : "bg-teal-50 text-teal-800",
      )}
    >
      <Phone className="h-3 w-3" />
      {statusLabel(status)}
    </span>
  );
}
