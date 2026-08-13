"use client";

import { AppShell } from "@/components/app-shell";
import { PaviAssistant } from "@/components/pavi/PaviAssistant";
import { useRequireAuth } from "@/lib/use-require-auth";

export default function PaviPage() {
  const { ready } = useRequireAuth();
  if (!ready) return null;
  return (
    <AppShell compact>
      <PaviAssistant />
    </AppShell>
  );
}
