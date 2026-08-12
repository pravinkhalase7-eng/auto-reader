"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { ContentTypeBadge, LanguageBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { api } from "@/lib/api";
import type { LessonCard as LessonCardType } from "@/types";

export function LessonCardView({
  lesson,
  onDeleted,
}: {
  lesson: LessonCardType;
  onDeleted?: () => void;
}) {
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState(false);

  async function remove(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (lesson.is_demo) return;
    if (!window.confirm(`Delete “${lesson.title}”? This removes the story from your library.`)) return;
    setDeleting(true);
    try {
      await api(`/lessons/${lesson.id}`, { method: "DELETE" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lessons"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["lesson", lesson.id] }),
      ]);
      onDeleted?.();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Could not delete this story.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Card className="relative h-full transition hover:-translate-y-0.5 hover:shadow-lg">
      {!lesson.is_demo ? (
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="absolute right-3 top-3 h-9 w-9 text-rose-700 hover:bg-rose-50"
          aria-label={`Delete ${lesson.title}`}
          disabled={deleting}
          onClick={remove}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      ) : null}
      <Link
        href={`/lessons/${lesson.id}`}
        className="block pr-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 rounded-3xl"
      >
        <div className="mb-3 flex flex-wrap gap-2">
          <LanguageBadge code={lesson.language} />
          <ContentTypeBadge type={lesson.content_type} />
          {lesson.page_count > 1 ? (
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-950">
              {lesson.page_count} pages
            </span>
          ) : null}
          {lesson.class_level ? (
            <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-900">
              Class {lesson.class_level}
            </span>
          ) : null}
        </div>
        <h3 className="font-display text-xl font-semibold text-teal-950">{lesson.title}</h3>
        {lesson.summary ? (
          <p className="mt-2 line-clamp-2 text-sm text-teal-900/70">{lesson.summary}</p>
        ) : null}
        <div className="mt-4 space-y-2">
          <div className="flex justify-between text-xs font-medium text-teal-900/60">
            <span>Progress</span>
            <span>{Math.round(lesson.progress_percent)}%</span>
          </div>
          <ProgressBar value={lesson.progress_percent} label={`${lesson.title} progress`} />
          {lesson.last_score != null ? (
            <p className="text-xs text-teal-800">Last score: {Math.round(lesson.last_score)}%</p>
          ) : null}
        </div>
      </Link>
    </Card>
  );
}
