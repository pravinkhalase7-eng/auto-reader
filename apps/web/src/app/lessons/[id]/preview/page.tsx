"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Image as ImageIcon, Sparkles } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { ContentTypeBadge, LanguageBadge } from "@/components/badges";
import { StoryIllustrations } from "@/components/story-illustrations";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, getToken } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import type { LessonCard } from "@/types";

type LessonDetail = LessonCard & {
  original_text?: string | null;
  edited_text?: string | null;
  pages: { id: string; page_number: number; original_storage_key: string }[];
};

export default function LessonPreviewPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showImage, setShowImage] = useState(true);
  const [pageImages, setPageImages] = useState<{ page: number; url: string }[]>([]);
  const [activePage, setActivePage] = useState(0);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data: lesson, isLoading } = useQuery({
    queryKey: ["lesson", id],
    queryFn: () => api<LessonDetail>(`/lessons/${id}`),
    enabled: !!token && !!id,
  });

  useEffect(() => {
    if (!lesson) return;
    setText(lesson.edited_text || lesson.original_text || "");
    setTitle(lesson.title || "");
  }, [lesson]);

  // Load original pages with auth header (img src can't send Bearer token)
  useEffect(() => {
    const urls: string[] = [];
    let cancelled = false;
    async function loadImages() {
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
      if (!cancelled) {
        setPageImages(loaded);
        setActivePage(0);
      }
    }
    void loadImages();
    return () => {
      cancelled = true;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [lesson?.pages, token]);

  const dirty = useMemo(() => {
    if (!lesson) return false;
    const original = lesson.edited_text || lesson.original_text || "";
    return text.trim() !== original.trim() || title.trim() !== (lesson.title || "").trim();
  }, [lesson, text, title]);

  async function continueToLearn() {
    if (!text.trim()) {
      setError("Please keep some lesson text before continuing.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const current = lesson?.edited_text || lesson?.original_text || "";
      if (text.trim() !== current.trim() || title.trim() !== (lesson?.title || "").trim()) {
        await api(`/lessons/${id}/text`, {
          method: "PATCH",
          body: JSON.stringify({ edited_text: text, title: title.trim() || undefined }),
        });
      }
      router.push(`/lessons/${id}/read`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your edits.");
    } finally {
      setSaving(false);
    }
  }

  if (!token) return null;

  return (
    <AppShell>
      <div className="mb-6">
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-teal-800">
          <Sparkles className="h-4 w-4" /> Preview & clean up
        </p>
        <h1 className="font-display mt-1 text-3xl font-bold text-teal-950 md:text-4xl">
          Check the story before we learn
        </h1>
        <p className="mt-2 max-w-2xl text-teal-900/75">
          Remove extra OCR noise (headers, page numbers, junk characters), fix any wrong words, then
          continue to listen and learn.
        </p>
      </div>

      {isLoading || !lesson ? (
        <p>Loading your page...</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <LanguageBadge code={lesson.language} />
              <ContentTypeBadge type={lesson.content_type} />
            </div>

            <label className="block text-sm font-semibold text-teal-900">
              Lesson title
              <input
                className="mt-1 w-full rounded-2xl border border-teal-900/15 bg-white px-4 py-3 text-lg font-semibold text-teal-950"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                aria-label="Lesson title"
              />
            </label>

            <label className="block text-sm font-semibold text-teal-900">
              Story text (editable)
              <textarea
                className="mt-1 min-h-[420px] w-full rounded-2xl border border-teal-900/15 bg-white p-4 text-base leading-relaxed text-teal-950"
                value={text}
                onChange={(e) => setText(e.target.value)}
                spellCheck
                aria-label="Editable lesson text"
              />
            </label>

            <p className="text-xs text-teal-900/55">
              Tip: delete chrome like website menus, ads, page numbers, or repeated headers. Keep blank
              lines between paragraphs.
              {dirty ? " · Unsaved changes will be applied when you continue." : ""}
            </p>

            {error ? <p className="text-sm text-rose-700">{error}</p> : null}

            <div className="flex flex-wrap gap-3 pt-2">
              <Button
                size="lg"
                variant="outline"
                onClick={async () => {
                  setSaving(true);
                  setError("");
                  try {
                    const res = await api<{ cleaned_text: string }>(`/lessons/${id}/clean-text`, {
                      method: "POST",
                      body: JSON.stringify({ edited_text: text }),
                    });
                    setText(res.cleaned_text);
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Could not clean the text.");
                  } finally {
                    setSaving(false);
                  }
                }}
                disabled={saving || !text.trim()}
              >
                Clean extra noise
              </Button>
              <Button size="lg" onClick={continueToLearn} disabled={saving}>
                {saving ? "Saving..." : "Looks good — Start learning"}
                <ArrowRight className="h-4 w-4" />
              </Button>
              {!lesson.is_demo ? (
                <Button
                  size="lg"
                  variant="outline"
                  onClick={() => router.push(`/lessons/${id}?continue=1`)}
                  disabled={saving}
                >
                  Add more pages
                </Button>
              ) : null}
              <Button
                size="lg"
                variant="outline"
                onClick={() => router.push(`/lessons/${id}`)}
                disabled={saving}
              >
                Back
              </Button>
            </div>
          </Card>

          <aside className="space-y-4">
            <Card className="bg-amber-50/80">
              <p className="font-display text-xl font-semibold text-teal-950">AI Teacher</p>
              <p className="mt-2 text-sm text-teal-900/75">
                I read your photo{lesson.page_count > 1 ? "s" : ""}. Please fix anything that looks
                wrong, then we&apos;ll practice together.
              </p>
            </Card>

            <Card>
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="font-semibold text-teal-950">
                  Original {pageImages.length > 1 ? "pages" : "page"}
                </p>
                <Button variant="ghost" size="sm" onClick={() => setShowImage((v) => !v)}>
                  <ImageIcon className="h-4 w-4" />
                  {showImage ? "Hide" : "Show"}
                </Button>
              </div>
              {showImage ? (
                pageImages.length ? (
                  <div className="space-y-3">
                    {pageImages.length > 1 ? (
                      <div className="flex flex-wrap gap-2">
                        {pageImages.map((img, i) => (
                          <Button
                            key={img.url}
                            size="sm"
                            variant={i === activePage ? "default" : "outline"}
                            onClick={() => setActivePage(i)}
                          >
                            Page {img.page}
                          </Button>
                        ))}
                      </div>
                    ) : null}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={pageImages[activePage]?.url}
                      alt={`Uploaded textbook page ${pageImages[activePage]?.page ?? 1}`}
                      className="max-h-[70vh] w-full rounded-2xl object-contain"
                    />
                  </div>
                ) : (
                  <p className="text-sm text-teal-900/60">
                    {lesson.pages?.length
                      ? "Loading original photos..."
                      : "No original photo for this lesson (demo text)."}
                  </p>
                )
              ) : null}
            </Card>
            {id ? <StoryIllustrations lessonId={id} paragraphCount={1} /> : null}
          </aside>
        </div>
      )}
    </AppShell>
  );
}
