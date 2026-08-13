"use client";

import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getPreferences, updatePreferences } from "@/lib/pavi-api";
import { useRequireAuth } from "@/lib/use-require-auth";

export default function SettingsPage() {
  const { ready } = useRequireAuth();
  const prefs = useQuery({ queryKey: ["pavi-prefs"], queryFn: getPreferences, enabled: ready });
  const [phone, setPhone] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [language, setLanguage] = useState("en");
  const [calls, setCalls] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!prefs.data) return;
    setTimezone(prefs.data.timezone);
    setLanguage(prefs.data.preferred_language);
    setCalls(prefs.data.phone_call_enabled);
  }, [prefs.data]);

  const save = useMutation({
    mutationFn: () =>
      updatePreferences({
        phone_number: phone || undefined,
        timezone,
        preferred_language: language,
        phone_call_enabled: calls,
      }),
    onSuccess: () => setSaved(true),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaved(false);
    save.mutate();
  }

  if (!ready) return null;

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold text-teal-950">Settings</h1>
      <Card className="mt-6 max-w-lg space-y-3">
        <p className="font-semibold text-teal-950">UI language</p>
        <p className="text-sm text-teal-900/70">
          English (lesson language stays independent — Hindi/Marathi lessons still quiz in those languages).
        </p>
        <p className="font-semibold text-teal-950">Reading speed default</p>
        <p className="text-sm text-teal-900/70">Slow — comfortable for children (change anytime in the reader).</p>
      </Card>
      <Card className="mt-6 max-w-lg">
        <h2 className="font-display text-xl font-semibold text-teal-950">Pavi phone reminders</h2>
        <form className="mt-4 space-y-3" onSubmit={onSubmit}>
          <label className="block text-sm font-medium text-teal-900">
            Phone number
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 98XXXXXXXX"
              className="mt-1 w-full rounded-xl border border-teal-900/15 px-3 py-2"
            />
          </label>
          {prefs.data?.phone_number_masked ? (
            <p className="text-xs text-teal-800/60">Saved number: {prefs.data.phone_number_masked}. Type a new number only if you want to change it.</p>
          ) : (
            <p className="text-xs text-amber-800">Required for phone reminders. Use E.164, for example +917219584184.</p>
          )}
          <label className="block text-sm font-medium text-teal-900">
            Timezone
            <input value={timezone} onChange={(e) => setTimezone(e.target.value)} className="mt-1 w-full rounded-xl border border-teal-900/15 px-3 py-2" />
          </label>
          <label className="block text-sm font-medium text-teal-900">
            Preferred language
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="mt-1 w-full rounded-xl border border-teal-900/15 px-3 py-2">
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="mr">Marathi</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-teal-900">
            <input type="checkbox" checked={calls} onChange={(e) => setCalls(e.target.checked)} />
            Enable phone call reminders
          </label>
          {saved && <p className="text-sm text-emerald-700">Saved.</p>}
          <Button type="submit" disabled={save.isPending}>Save Pavi settings</Button>
        </form>
      </Card>
    </AppShell>
  );
}
