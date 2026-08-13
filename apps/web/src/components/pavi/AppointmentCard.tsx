"use client";

import { MapPin, Phone } from "lucide-react";
import { Card } from "@/components/ui/card";
import { CallStatusBadge } from "@/components/pavi/CallStatusBadge";
import type { Appointment } from "@/types/pavi";

export function AppointmentCard({ appointment }: { appointment: Appointment }) {
  return (
    <Card className="space-y-1.5 rounded-2xl p-3.5 shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-teal-950">{appointment.title}</p>
          <p className="text-sm text-teal-800/70">{appointment.when_label}</p>
        </div>
        <CallStatusBadge status={appointment.status} />
      </div>
      {appointment.location && (
        <p className="flex items-center gap-1.5 text-sm text-teal-800/80">
          <MapPin className="h-3.5 w-3.5" /> {appointment.location}
        </p>
      )}
      {appointment.phone_call_enabled && (
        <p className="flex items-center gap-1.5 text-sm text-teal-800/80">
          <Phone className="h-3.5 w-3.5" /> Voice reminder enabled
        </p>
      )}
    </Card>
  );
}
