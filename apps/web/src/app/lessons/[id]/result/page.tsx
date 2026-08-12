"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { AttemptResult } from "@/types";
import { useAuthStore } from "@/store/auth-store";

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const [result, setResult] = useState<AttemptResult | null>(null);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  useEffect(() => {
    const raw = sessionStorage.getItem(`attempt-${id}`);
    if (raw) setResult(JSON.parse(raw));
  }, [id]);

  if (!token) return null;

  const score = result ? Math.round(result.score) : 0;
  const max = result ? Math.round(result.max_score) : 0;
  const accuracy = result ? Math.round(result.accuracy * 100) : 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-5xl" aria-hidden>
          🎉
        </p>
        <h1 className="font-display mt-3 text-4xl font-bold text-teal-950">Great Job!</h1>
        <p className="mt-2 text-teal-900/70">{result?.message || "Here are your results."}</p>

        <Card className="mt-8">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-semibold text-teal-900/50">Score</p>
              <p className="font-display text-4xl font-bold text-teal-950">
                {score} / {max}
              </p>
            </div>
            <div>
              <p className="text-sm font-semibold text-teal-900/50">Accuracy</p>
              <p className="font-display text-4xl font-bold text-teal-950">{accuracy}%</p>
            </div>
          </div>

          <div className="mt-8 grid gap-4 text-left md:grid-cols-2">
            <div>
              <h3 className="font-semibold text-teal-900">Topics understood</h3>
              <ul className="mt-2 space-y-1 text-sm text-teal-900/80">
                {(result?.topics_understood || ["Keep practicing!"]).map((t) => (
                  <li key={t}>• {t}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-semibold text-teal-900">Needs practice</h3>
              <ul className="mt-2 space-y-1 text-sm text-teal-900/80">
                {(result?.needs_practice?.length ? result.needs_practice : ["You're doing great!"]).map(
                  (t) => (
                    <li key={t}>• {t}</li>
                  ),
                )}
              </ul>
            </div>
          </div>
        </Card>

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button asChild size="lg">
            <Link href={`/lessons/${id}/read`}>Read Again</Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link href={`/lessons/${id}/quiz`}>Try Quiz Again</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/dashboard">Back to Home</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
