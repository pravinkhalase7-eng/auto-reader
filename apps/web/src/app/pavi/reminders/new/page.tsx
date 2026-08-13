"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { createReminder, getPreferences } from "@/lib/pavi-api";
import { ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/use-require-auth";
import { PaviConfirmationCard } from "@/components/pavi/PaviConfirmationCard";

export default function NewReminderPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const prefs = useQuery({ queryKey: ["pavi-prefs"], queryFn: getPreferences, enabled: ready });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [phoneCall, setPhoneCall] = useState(true);
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("en");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!prefs.data) return;
    setTimezone(prefs.data.timezone);
    setLanguage(prefs.data.preferred_language);
    setPhoneCall(prefs.data.phone_call_enabled);
  }, [prefs.data]);

  const save = useMutation({
    mutationFn: () =>
      createReminder({
        title,
        description,
        reminder_time: `${date}T${time}`,
        timezone,
        phone_call_enabled: phoneCall,
        phone_number: phone || undefined,
        language,
        recurrence_rule: repeat || undefined,
        reminder_type: phoneCall ? "both" : "notification",
      }),
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "I couldn't save that reminder right now. Please try again.");
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutate();
  }

  if (!ready) return null;

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold text-teal-950">New reminder</h1>
      <p className="mt-1 text-teal-900/70">Same service as Pavi chat — use this when you want a form instead of talking.</p>
      <Card className="mt-6 max-w-xl">
        {save.data ? (
          <div className="space-y-4">
            <PaviConfirmationCard
              confirmation={{
                kind: "reminder",
                title: save.data.title,
                when_label: save.data.when_label,
                phone_call_enabled: save.data.phone_call_enabled,
              }}
            />
            <Button onClick={() => router.push("/pavi")}>Back to Pavi</Button>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={onSubmit}>
            <Field label="Title">
              <input required value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
            </Field>
            <Field label="Description">
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} className={inputClass} rows={3} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Date">
                <input required type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} />
              </Field>
              <Field label="Time">
                <input required type="time" value={time} onChange={(e) => setTime(e.target.value)} className={inputClass} />
              </Field>
            </div>
            <Field label="Timezone">
              <input value={timezone} onChange={(e) => setTimezone(e.target.value)} className={inputClass} />
            </Field>
            <label className="flex items-center gap-2 text-sm text-teal-900">
              <input type="checkbox" checked={phoneCall} onChange={(e) => setPhoneCall(e.target.checked)} />
              Phone call reminder
            </label>
            <Field label="Phone number (E.164)">
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+9198XXXXXXXX" className={inputClass} />
            </Field>
            <Field label="Language">
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className={inputClass}>
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="mr">Marathi</option>
              </select>
            </Field>
            <Field label="Repeat">
              <select value={repeat} onChange={(e) => setRepeat(e.target.value)} className={inputClass}>
                <option value="">Does not repeat</option>
                <option value="FREQ=DAILY">Every day</option>
                <option value="FREQ=WEEKLY;BYDAY=MO">Every Monday</option>
              </select>
            </Field>
            {error && <p className="text-sm text-rose-700">{error}</p>}
            <Button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save reminder"}</Button>
          </form>
        )}
      </Card>
    </AppShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-sm font-medium text-teal-900">
      <span>{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-xl border border-teal-900/15 bg-white px-3 py-2 text-sm font-normal text-teal-950 outline-none focus:ring-2 focus:ring-teal-600";
