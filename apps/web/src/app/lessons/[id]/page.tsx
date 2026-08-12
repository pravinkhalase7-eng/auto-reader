"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Headphones, HelpCircle, Image as ImageIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ContentTypeBadge, LanguageBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import type { LessonCard } from "@/types";

type LessonDetail = LessonCard & {
  original_text?: string | null;
  edited_text?: string | null;
  pages: { id: string; page_number: number; original_storage_key: string }[];
};

export default function LessonHubPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const [showOriginal, setShowOriginal] = useState(false);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data: lesson } = useQuery({
    queryKey: ["lesson", id],
    queryFn: () => api<LessonDetail>(`/lessons/${id}`),
    enabled: !!token && !!id,
  });

  if (!token) return null;

  return (
    <AppShell>
      {!lesson ? (
        <p>Loading your lesson...</p>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
          <div>
            <div className="mb-4 flex flex-wrap gap-2">
              <LanguageBadge code={lesson.language} />
              <ContentTypeBadge type={lesson.content_type} />
            </div>
            <h1 className="font-display text-4xl font-bold text-teal-950">{lesson.title}</h1>
            {lesson.summary ? <p className="mt-3 text-lg text-teal-900/75">{lesson.summary}</p> : null}
            <Card className="mt-6">
              <p className="whitespace-pre-wrap text-teal-950 leading-relaxed">
                {(lesson.edited_text || lesson.original_text || "").slice(0, 600)}
                {(lesson.edited_text || lesson.original_text || "").length > 600 ? "…" : ""}
              </p>
            </Card>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link href={`/lessons/${id}/preview`}>
                  <BookOpen className="h-4 w-4" /> Review & learn
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary">
                <Link href={`/lessons/${id}/read`}>
                  <Headphones className="h-4 w-4" /> Start reading
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href={`/lessons/${id}/quiz`}>
                  <HelpCircle className="h-4 w-4" /> Quiz me
                </Link>
              </Button>
              <Button variant="outline" onClick={() => setShowOriginal(true)}>
                <ImageIcon className="h-4 w-4" /> View Original Page
              </Button>
            </div>
          </div>

          <aside className="space-y-4">
            <Card className="bg-gradient-to-br from-amber-50 to-white">
              <p className="text-sm font-semibold uppercase tracking-wide text-amber-800/70">AI Teacher</p>
              <p className="font-display mt-2 text-2xl font-semibold text-teal-950">
                Great! Let&apos;s read this together.
              </p>
              <p className="mt-2 text-sm text-teal-900/70">
                Listen carefully, follow the highlighted words, then I&apos;ll ask you some questions.
              </p>
              <div className="mt-4 flex flex-col gap-2">
                <Button asChild>
                  <Link href={`/lessons/${id}/preview`}>Review text first</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href={`/lessons/${id}/read`}>Listen + Read</Link>
                </Button>
                <Button asChild variant="secondary">
                  <Link href={`/lessons/${id}/quiz`}>Quiz Me</Link>
                </Button>
              </div>
            </Card>
          </aside>
        </div>
      )}

      {showOriginal && lesson?.pages?.[0] ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-teal-950/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Original page"
          onClick={() => setShowOriginal(false)}
        >
          <div className="max-h-[90vh] max-w-3xl overflow-auto rounded-3xl bg-white p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex justify-between">
              <h2 className="font-display text-xl font-semibold">Original page</h2>
              <Button variant="ghost" onClick={() => setShowOriginal(false)}>
                Close
              </Button>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${API_URL}/storage/${lesson.pages[0].original_storage_key}`}
              alt="Original uploaded page"
              className="w-full rounded-2xl"
            />
            <p className="mt-2 text-xs text-teal-900/60">
              Compare this with the text your AI Teacher read for you.
            </p>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
