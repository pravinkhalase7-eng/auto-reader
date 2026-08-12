"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ProcessingAnimation } from "@/components/processing-animation";
import { UploadZone } from "@/components/upload-zone";
import { Button } from "@/components/ui/button";
import { api, getToken } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import type { JobStatus, UploadResponse } from "@/types";
import { useAuthStore } from "@/store/auth-store";

export default function UploadPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const [files, setFiles] = useState<File[]>([]);
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

  async function submit() {
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
      const data = (await res.json()) as UploadResponse;
      setJob({
        id: data.job_id,
        lesson_id: data.lesson_id,
        status: "running",
        current_step: "uploaded",
        progress_percent: 10,
        message: data.message,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  if (!token) return null;

  return (
    <AppShell>
      {job && job.status !== "failed" ? (
        <ProcessingAnimation
          currentStep={job.current_step}
          progress={job.progress_percent}
          message={job.message}
        />
      ) : (
        <div className="mx-auto max-w-3xl">
          <h1 className="font-display text-3xl font-bold text-teal-950 md:text-4xl">Upload your lesson</h1>
          <p className="mt-2 text-teal-900/75">
            Take a photo of a textbook page and let your AI Teacher teach you.
          </p>
          <div className="mt-8">
            <UploadZone files={files} onChange={setFiles} />
          </div>
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
          {job?.status === "failed" ? (
            <p className="mt-4 text-sm text-rose-700">{job.error_message || job.message}</p>
          ) : null}
          <div className="mt-6">
            <Button size="lg" disabled={!files.length || uploading} onClick={submit}>
              {uploading ? "Uploading..." : "Teach me this lesson"}
            </Button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
