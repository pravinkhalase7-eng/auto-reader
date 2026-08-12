"use client";

import Link from "next/link";
import { ContentTypeBadge, LanguageBadge } from "@/components/badges";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import type { LessonCard as LessonCardType } from "@/types";

export function LessonCardView({ lesson }: { lesson: LessonCardType }) {
  return (
    <Link href={`/lessons/${lesson.id}`} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 rounded-3xl">
      <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-lg">
        <div className="mb-3 flex flex-wrap gap-2">
          <LanguageBadge code={lesson.language} />
          <ContentTypeBadge type={lesson.content_type} />
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
      </Card>
    </Link>
  );
}
