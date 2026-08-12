"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Headphones, HelpCircle, Image as ImageIcon, ImagePlus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ContentTypeBadge, LanguageBadge } from "@/components/badges";
import { ProcessingAnimation } from "@/components/processing-animation";
import { StoryIllustrations } from "@/components/story-illustrations";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { UploadZone } from "@/components/upload-zone";
import { api, getToken } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import type { JobStatus, LessonCard, UploadResponse } from "@/types";

type LessonDetail = LessonCard & {
  original_text?: string | null;
  edited_text?: string | null;
  pages: { id: string; page_number: number; original_storage_key: string }[];
};

export default function LessonHubPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showOriginal, setShowOriginal] = useState(false);
  const [addingPages, setAddingPages] = useState(false);
  const [extraFiles, setExtraFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [pageImages, setPageImages] = useState<{ page: number; url: string }[]>([]);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (new URLSearchParams(window.location.search).get("continue") === "1") {
      setAddingPages(true);
    }
  }, []);

  const { data: lesson } = useQuery({
    queryKey: ["lesson", id],
    queryFn: () => api<LessonDetail>(`/lessons/${id}`),
    enabled: !!token && !!id,
  });

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = setInterval(async () => {
      try {
        const next = await api<JobStatus>(`/lessons/${job.lesson_id}/jobs/${job.id}`);
        setJob(next);
        if (next.status === "completed") {
          await queryClient.invalidateQueries({ queryKey: ["lesson", id] });
          router.push(`/lessons/${id}/preview`);
        }
      } catch {
        /* keep polling */
      }
    }, 1200);
    return () => clearInterval(timer);
  }, [job, router, id, queryClient]);

  useEffect(() => {
    const urls: string[] = [];
    let cancelled = false;
    async function load() {
      const pages = [...(lesson?.pages || [])].sort((a, b) => a.page_number - b.page_number);
      if (!pages.length || !token) {
        setPageImages([]);
        return;
      }
      const loaded: { page: number; url: string }[] = [];
      for (const page of pages) {
        try {
          const res = await fetch(`${API_URL}/storage/${page.original_storage_key}`, {
            headers: { Authorization: `Bearer ${getToken()}` },
          });
          if (!res.ok) continue;
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          if (cancelled) {
            URL.revokeObjectURL(url);
            continue;
          }
          urls.push(url);
          loaded.push({ page: page.page_number, url });
        } catch {
          /* skip missing page */
        }
      }
      if (!cancelled) setPageImages(loaded);
    }
    void load();
    return () => {
      cancelled = true;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [lesson?.pages, token]);

  async function addPages() {
    if (!extraFiles.length || !id) return;
    setUploading(true);
    setError("");
    try {
      const fd = new FormData();
      extraFiles.forEach((f) => fd.append("files", f));
      const data = await api<UploadResponse>(`/lessons/${id}/pages`, { method: "POST", body: fd });
      setJob({
        id: data.job_id,
        lesson_id: data.lesson_id,
        status: "running",
        current_step: "uploaded",
        progress_percent: 10,
        message: data.message,
      });
      setAddingPages(false);
      setExtraFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add those pages.");
    } finally {
      setUploading(false);
    }
  }

  async function removeStory() {
    if (!lesson || lesson.is_demo) return;
    if (!window.confirm(`Delete “${lesson.title}”? This removes the story from your library.`)) return;
    setDeleting(true);
    setError("");
    try {
      await api(`/lessons/${id}`, { method: "DELETE" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lessons"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
      router.push("/lessons");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this story.");
    } finally {
      setDeleting(false);
    }
  }

  if (!token) return null;

  if (job && job.status !== "failed") {
    return (
      <AppShell>
        <ProcessingAnimation
          currentStep={job.current_step}
          progress={job.progress_percent}
          message={job.message}
        />
      </AppShell>
    );
  }

  const ownStory = Boolean(lesson && !lesson.is_demo);

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
              {lesson.page_count > 1 ? (
                <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-950">
                  {lesson.page_count} pages
                </span>
              ) : null}
            </div>
            <h1 className="font-display text-4xl font-bold text-teal-950">{lesson.title}</h1>
            {lesson.summary ? <p className="mt-3 text-lg text-teal-900/75">{lesson.summary}</p> : null}
            <Card className="mt-6">
              <p className="whitespace-pre-wrap text-teal-950 leading-relaxed">
                {(lesson.edited_text || lesson.original_text || "").slice(0, 600)}
                {(lesson.edited_text || lesson.original_text || "").length > 600 ? "…" : ""}
              </p>
            </Card>
            {error || job?.status === "failed" ? (
              <p className="mt-4 text-sm text-rose-700">
                {error || job?.error_message || job?.message}
              </p>
            ) : null}
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
              {lesson.pages.length ? (
                <Button variant="outline" onClick={() => setShowOriginal(true)}>
                  <ImageIcon className="h-4 w-4" /> View original pages
                </Button>
              ) : null}
              {ownStory && lesson.pages.length ? (
                <Button variant="outline" onClick={() => setAddingPages((v) => !v)}>
                  <ImagePlus className="h-4 w-4" /> Add more pages
                </Button>
              ) : null}
              {ownStory ? (
                <Button variant="danger" disabled={deleting} onClick={removeStory}>
                  <Trash2 className="h-4 w-4" /> {deleting ? "Deleting..." : "Delete story"}
                </Button>
              ) : null}
            </div>

            {addingPages && ownStory && lesson.pages.length ? (
              <Card className="mt-6 space-y-4">
                <div>
                  <h2 className="font-display text-xl font-semibold text-teal-950">Continue this story</h2>
                  <p className="mt-1 text-sm text-teal-900/70">
                    Upload the next pages in order. I&apos;ll stitch them onto this lesson and keep reading.
                  </p>
                </div>
                <UploadZone files={extraFiles} onChange={setExtraFiles} />
                <Button size="lg" disabled={!extraFiles.length || uploading} onClick={addPages}>
                  {uploading
                    ? "Uploading..."
                    : extraFiles.length > 1
                      ? `Add ${extraFiles.length} pages and continue`
                      : "Add page and continue"}
                </Button>
              </Card>
            ) : null}
          </div>

          <aside className="space-y-4">
            <Card className="bg-gradient-to-br from-amber-50 to-white">
              <p className="text-sm font-semibold uppercase tracking-wide text-amber-800/70">AI Teacher</p>
              <p className="font-display mt-2 text-2xl font-semibold text-teal-950">
                Great! Let&apos;s read this together.
              </p>
              <p className="mt-2 text-sm text-teal-900/70">
                Listen carefully, follow the highlighted words, then I&apos;ll ask you some questions.
                {ownStory
                  ? lesson.page_count
                    ? " Photograph the next page whenever the story continues."
                    : " You can add textbook photos later if you have them."
                  : ""}
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
            {id ? <StoryIllustrations lessonId={id} paragraphCount={1} /> : null}
          </aside>
        </div>
      )}

      {showOriginal && lesson ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-teal-950/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Original pages"
          onClick={() => setShowOriginal(false)}
        >
          <div
            className="max-h-[90vh] max-w-3xl overflow-auto rounded-3xl bg-white p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex justify-between">
              <h2 className="font-display text-xl font-semibold">Original pages</h2>
              <Button variant="ghost" onClick={() => setShowOriginal(false)}>
                Close
              </Button>
            </div>
            {pageImages.length ? (
              <div className="space-y-4">
                {pageImages.map((img) => (
                  <figure key={img.url}>
                    <figcaption className="mb-2 text-sm font-semibold text-teal-900">
                      Page {img.page}
                    </figcaption>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={img.url} alt={`Original page ${img.page}`} className="w-full rounded-2xl" />
                  </figure>
                ))}
              </div>
            ) : (
              <p className="text-sm text-teal-900/60">No original photos for this lesson (demo text).</p>
            )}
            <p className="mt-2 text-xs text-teal-900/60">
              Compare these with the text your AI Teacher read for you.
            </p>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
