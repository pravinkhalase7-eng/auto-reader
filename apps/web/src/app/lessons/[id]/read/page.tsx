"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { LessonViewer } from "@/components/lesson-viewer";
import { ReadingPlayer } from "@/components/reading-player";
import { StoryIllustrations, useStoryIllustrationAssets } from "@/components/story-illustrations";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import type { AudioAsset, LessonContent } from "@/types";

export default function ReadPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const router = useRouter();

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const contentQuery = useQuery({
    queryKey: ["content", id],
    queryFn: () => api<LessonContent>(`/lessons/${id}/content`),
    enabled: !!token && !!id,
  });

  const audioQuery = useQuery({
    queryKey: ["audio", id],
    queryFn: () => api<AudioAsset>(`/lessons/${id}/audio`),
    enabled: !!token && !!id,
  });

  const illustrations = useStoryIllustrationAssets(id || "");

  if (!token) return null;
  const content = contentQuery.data;
  const paragraphCount =
    content?.sections.reduce((sum, section) => sum + section.paragraphs.length, 0) ?? 0;

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-teal-800/70">AI Teacher</p>
          <h1 className="font-display text-3xl font-bold text-teal-950">
            {content?.title || "Reading..."}
          </h1>
          <p className="text-teal-900/70">Let&apos;s read this together!</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link href={`/lessons/${id}/preview`}>Edit text</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href={`/lessons/${id}/quiz`}>Quiz Me</Link>
          </Button>
        </div>
      </div>

      {contentQuery.isError ? (
        <p className="mb-4 text-sm text-rose-700">
          {contentQuery.error instanceof Error
            ? contentQuery.error.message
            : "I couldn't load this lesson."}
        </p>
      ) : null}

      {id ? (
        <div className="mb-6">
          <StoryIllustrations lessonId={id} paragraphCount={paragraphCount} />
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.5fr_0.9fr]">
        <Card className="max-h-[70vh] overflow-y-auto p-6 md:p-8">
          {content ? (
            <LessonViewer
              content={content}
              scenes={illustrations.scenes}
              urls={illustrations.urls}
            />
          ) : (
            <p>Preparing your lesson...</p>
          )}
        </Card>
        <div className="space-y-4">
          {content ? <ReadingPlayer content={content} audio={audioQuery.data || null} /> : null}
          <Card className="bg-amber-50/80">
            <p className="font-display text-xl font-semibold text-teal-950">Listen carefully.</p>
            <p className="mt-2 text-sm text-teal-900/70">
              <strong>Direct reading</strong> narrates the story like a teacher, with no word
              highlight. Use <strong>Natural reading</strong> or <strong>Word by word</strong> when
              you want the spoken word to light up.
            </p>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
