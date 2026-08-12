"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ImagePlus, PenLine } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { ProcessingAnimation } from "@/components/processing-animation";
import { UploadZone } from "@/components/upload-zone";
import { Button } from "@/components/ui/button";
import { api, getToken } from "@/lib/api";
import { API_URL, cn } from "@/lib/utils";
import type { JobStatus, UploadResponse } from "@/types";
import { useAuthStore } from "@/store/auth-store";

type StoryMode = "text" | "photos";

const MIN_STORY_CHARS = 20;

export default function UploadPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const [mode, setMode] = useState<StoryMode>("text");
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [storyText, setStoryText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const id = setInterval(async () => {
      try {
        const next = await api<JobStatus>(`/lessons/${job.lesson_id}/jobs/${job.id}`);
        setJob(next);
        if (next.status === "completed") {
          router.push(`/lessons/${next.lesson_id}/preview`);
        }
      } catch {
        /* keep polling */
      }
    }, 1200);
    return () => clearInterval(id);
  }, [job, router]);

  async function startFromJob(data: UploadResponse) {
    setJob({
      id: data.job_id,
      lesson_id: data.lesson_id,
      status: "running",
      current_step: "uploaded",
      progress_percent: 10,
      message: data.message,
    });
  }

  async function submitPhotos() {
    if (!files.length) return;
    setUploading(true);
    setError("");
    try {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      const res = await fetch(`${API_URL}/lessons/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail?.detail || data.detail || "Upload failed");
      }
      await startFromJob((await res.json()) as UploadResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function submitText() {
    const text = storyText.trim();
    if (text.length < MIN_STORY_CHARS) {
      setError("Type a little more of the story so I can teach it.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const data = await api<UploadResponse>("/lessons/from-text", {
        method: "POST",
        body: JSON.stringify({
          text,
          title: title.trim() || undefined,
        }),
      });
      await startFromJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the story");
    } finally {
      setUploading(false);
    }
  }

  if (!token) return null;

  const textReady = storyText.trim().length >= MIN_STORY_CHARS;

  return (
    <AppShell>
      {job && job.status !== "failed" ? (
        <ProcessingAnimation
          currentStep={job.current_step}
          progress={job.progress_percent}
          message={job.message}
          source={mode}
        />
      ) : (
        <div className="mx-auto max-w-3xl">
          <h1 className="font-display text-3xl font-bold text-teal-950 md:text-4xl">Add a story</h1>
          <p className="mt-2 text-teal-900/75">
            Type the story yourself, or photograph the textbook pages. I&apos;ll turn it into a lesson
            you can read, listen to, and quiz.
          </p>

          <div className="mt-8 grid gap-3 sm:grid-cols-2" role="tablist" aria-label="How to add the story">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "text"}
              onClick={() => {
                setMode("text");
                setError("");
              }}
              className={cn(
                "flex items-start gap-3 rounded-[1.75rem] border-2 p-5 text-left transition",
                mode === "text"
                  ? "border-teal-700 bg-teal-50 shadow-sm"
                  : "border-teal-900/15 bg-white/70 hover:border-teal-700/40",
              )}
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-800">
                <PenLine className="h-5 w-5" aria-hidden />
              </span>
              <span>
                <span className="block font-display text-lg font-semibold text-teal-950">Type a story</span>
                <span className="mt-1 block text-sm text-teal-900/70">
                  Paste or write the text. I&apos;ll skip photos and start teaching.
                </span>
              </span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "photos"}
              onClick={() => {
                setMode("photos");
                setError("");
              }}
              className={cn(
                "flex items-start gap-3 rounded-[1.75rem] border-2 p-5 text-left transition",
                mode === "photos"
                  ? "border-teal-700 bg-teal-50 shadow-sm"
                  : "border-teal-900/15 bg-white/70 hover:border-teal-700/40",
              )}
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-teal-100 text-teal-800">
                <ImagePlus className="h-5 w-5" aria-hidden />
              </span>
              <span>
                <span className="block font-display text-lg font-semibold text-teal-950">Upload photos</span>
                <span className="mt-1 block text-sm text-teal-900/70">
                  Photograph every page, in order. I&apos;ll read the pictures.
                </span>
              </span>
            </button>
          </div>

          <div className="mt-8" role="tabpanel">
            {mode === "text" ? (
              <div className="space-y-4">
                <label className="block">
                  <span className="mb-1.5 block text-sm font-semibold text-teal-900">Title (optional)</span>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={200}
                    placeholder="The Lion and the Mouse"
                    className="h-12 w-full rounded-2xl border border-teal-900/15 bg-white px-4 text-teal-950 outline-none ring-teal-600 placeholder:text-teal-900/35 focus:ring-2"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-sm font-semibold text-teal-900">Story</span>
                  <textarea
                    value={storyText}
                    onChange={(e) => setStoryText(e.target.value)}
                    rows={12}
                    maxLength={80000}
                    placeholder="Once upon a time, a lion was sleeping in the forest..."
                    className="w-full resize-y rounded-[1.5rem] border border-teal-900/15 bg-white px-4 py-3 text-base leading-relaxed text-teal-950 outline-none ring-teal-600 placeholder:text-teal-900/35 focus:ring-2"
                  />
                </label>
                <p className="text-xs text-teal-900/55">
                  {storyText.trim().length} characters
                  {storyText.trim().length > 0 && storyText.trim().length < MIN_STORY_CHARS
                    ? ` · need ${MIN_STORY_CHARS - storyText.trim().length} more`
                    : ""}
                </p>
              </div>
            ) : (
              <UploadZone files={files} onChange={setFiles} />
            )}
          </div>

          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
          {job?.status === "failed" ? (
            <p className="mt-4 text-sm text-rose-700">{job.error_message || job.message}</p>
          ) : null}
          <div className="mt-6">
            {mode === "text" ? (
              <Button size="lg" disabled={!textReady || uploading} onClick={submitText}>
                {uploading ? "Saving story..." : "Teach me this story"}
              </Button>
            ) : (
              <Button size="lg" disabled={!files.length || uploading} onClick={submitPhotos}>
                {uploading
                  ? "Uploading..."
                  : files.length > 1
                    ? `Teach me this ${files.length}-page story`
                    : "Teach me this lesson"}
              </Button>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}
