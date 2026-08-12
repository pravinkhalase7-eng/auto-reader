"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { LessonCardView } from "@/components/lesson-card";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import type { LessonCard } from "@/types";

function lessonSubjectKey(lesson: LessonCard) {
  return lesson.subject || lesson.language.toUpperCase();
}

function LessonsLibrary() {
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const searchParams = useSearchParams();
  const subject = searchParams.get("subject");

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data = [], isLoading } = useQuery({
    queryKey: ["lessons"],
    queryFn: () => api<LessonCard[]>("/lessons"),
    enabled: !!token,
  });

  if (!token) return null;

  const lessons = subject ? data.filter((l) => lessonSubjectKey(l) === subject) : data;

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold text-teal-950">
        {subject ? subject : "Lesson Library"}
      </h1>
      <p className="mt-2 text-teal-900/70">
        {subject
          ? `${lessons.length} lesson${lessons.length === 1 ? "" : "s"} in ${subject}.`
          : "All your lessons and demo stories in one place."}
      </p>
      {subject ? (
        <Link href="/lessons" className="mt-3 inline-block text-sm font-semibold text-teal-800 underline">
          View all subjects
        </Link>
      ) : null}
      {isLoading ? <p className="mt-8">Loading lessons...</p> : null}
      {!isLoading && subject && lessons.length === 0 ? (
        <p className="mt-8 text-teal-900/70">No lessons in this subject yet.</p>
      ) : null}
      <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {lessons.map((l) => (
          <LessonCardView key={l.id} lesson={l} />
        ))}
      </div>
    </AppShell>
  );
}

export default function LessonsPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <p>Loading lessons...</p>
        </AppShell>
      }
    >
      <LessonsLibrary />
    </Suspense>
  );
}
