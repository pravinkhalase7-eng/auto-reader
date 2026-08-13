"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ImageIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, getToken } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import { useReaderStore } from "@/store/reader-store";
import type { IllustrationsResponse, StoryIllustration } from "@/types";

const EMPTY_SCENES: StoryIllustration[] = [];
const DRAWING_TIMEOUT_MS = 120_000;

function normalizeIllustrations(raw: IllustrationsResponse | StoryIllustration[]): IllustrationsResponse {
  if (Array.isArray(raw)) {
    const geminiReady = raw.filter((scene) => scene.provider === "gemini").length;
    return {
      scenes: raw,
      status: geminiReady >= 4 ? "ready" : "drawing",
      message:
        geminiReady >= 4
          ? ""
          : "Drawing all four pictures at once — they usually appear in about 20 seconds.",
      gemini_ready: geminiReady,
    };
  }
  return raw;
}

export function downloadSceneImage(url: string, filename: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function useStoryIllustrationAssets(lessonId: string) {
  const [timedOut, setTimedOut] = useState(false);
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["illustrations", lessonId],
    queryFn: async () =>
      normalizeIllustrations(await api<IllustrationsResponse | StoryIllustration[]>(`/lessons/${lessonId}/illustrations`)),
    enabled: !!lessonId,
    refetchInterval: timedOut
      ? false
      : (query) => (query.state.data?.status === "drawing" ? 2000 : false),
  });

  useEffect(() => {
    if (data?.status !== "drawing") {
      setTimedOut(false);
      return;
    }
    const timer = window.setTimeout(() => setTimedOut(true), DRAWING_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [data?.status, lessonId]);

  const status = timedOut && data?.status === "drawing" ? "failed" : (data?.status ?? (isLoading ? "drawing" : "failed"));
  const message =
    timedOut && data?.status === "drawing"
      ? "This is taking longer than usual. The pictures may not be set up on this server, or Gemini is busy."
      : (data?.message ?? "");
  const allScenes = data?.scenes ?? EMPTY_SCENES;
  const scenes = useMemo(
    () => allScenes.filter((scene) => scene.provider === "gemini"),
    [allScenes],
  );
  const [urls, setUrls] = useState<Record<string, string>>({});
  const sceneKey = scenes.map((scene) => scene.id).join(",");

  useEffect(() => {
    const created: string[] = [];
    let cancelled = false;
    async function load() {
      const next: Record<string, string> = {};
      await Promise.all(
        scenes.map(async (scene) => {
          try {
            const res = await fetch(`${API_URL}/storage/${scene.storage_key}`, {
              headers: { Authorization: `Bearer ${getToken()}` },
            });
            if (!res.ok) return;
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            created.push(url);
            next[scene.id] = url;
          } catch {
            /* skip */
          }
        }),
      );
      if (!cancelled) setUrls(next);
    }
    if (scenes.length) {
      void load();
    } else {
      setUrls((prev) => (Object.keys(prev).length === 0 ? prev : {}));
    }
    return () => {
      cancelled = true;
      created.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [sceneKey, scenes]);

  return { scenes, urls, isLoading, isError, error, status, message, refetch };
}

export function sceneIndexForParagraph(
  paragraphIndex: number,
  paragraphCount: number,
  sceneCount: number,
) {
  if (!sceneCount) return -1;
  if (paragraphCount <= 1) return 0;
  const ratio = paragraphIndex / Math.max(1, paragraphCount - 1);
  return Math.min(sceneCount - 1, Math.max(0, Math.round(ratio * (sceneCount - 1))));
}

export function StoryIllustrations({
  lessonId,
  paragraphCount,
}: {
  lessonId: string;
  paragraphCount: number;
}) {
  const paragraphIndex = useReaderStore((s) => s.paragraphIndex);
  const queryClient = useQueryClient();
  const { scenes, urls, isLoading, isError, error, status, message, refetch } =
    useStoryIllustrationAssets(lessonId);
  const [drawing, setDrawing] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);

  const activeIndex = useMemo(
    () => sceneIndexForParagraph(paragraphIndex, paragraphCount, scenes.length),
    [paragraphCount, paragraphIndex, scenes.length],
  );

  useEffect(() => {
    setPicked(null);
  }, [paragraphIndex]);

  const index = picked ?? Math.max(0, activeIndex);

  async function redraw() {
    setDrawing(true);
    try {
      await api(`/lessons/${lessonId}/illustrations`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["illustrations", lessonId] });
      setPicked(null);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Could not draw the pictures.");
      await refetch();
    } finally {
      setDrawing(false);
    }
  }

  if (isLoading && status === "drawing" && !scenes.length) {
    return (
      <Card>
        <p className="text-sm text-teal-900/70">Looking for story pictures...</p>
      </Card>
    );
  }

  if (!scenes.length) {
    const waiting = status === "drawing" || drawing;
    return (
      <Card>
        <p className="font-display text-lg font-semibold text-teal-950">Story pictures</p>
        {waiting ? (
          <>
            <p className="mt-1 text-sm text-teal-900/70">
              {message || "Drawing all four pictures at once — they usually appear in about 20 seconds."}
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[1, 2, 3, 4].map((n) => (
                <div
                  key={n}
                  className="flex h-28 animate-pulse items-center justify-center rounded-2xl bg-teal-50 text-xs font-semibold text-teal-800/60"
                >
                  Picture {n}
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="mt-1 text-sm text-rose-700">
            {isError
              ? error instanceof Error
                ? error.message
                : "I couldn't load the story pictures."
              : message || "I couldn't draw the story pictures."}
          </p>
        )}
        <Button className="mt-3" variant="outline" disabled={drawing} onClick={redraw}>
          {drawing ? "Drawing the story..." : waiting ? "Still drawing — try again" : "Draw the story now"}
        </Button>
      </Card>
    );
  }

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="font-display text-lg font-semibold text-teal-950">Story pictures</p>
        <span className="text-xs font-semibold text-teal-800/70">
          {scenes.length} scenes
        </span>
      </div>
      {status === "drawing" ? (
        <p className="text-sm text-teal-900/70">
          Follow the pictures in order. More scenes are still being drawn.
        </p>
      ) : status === "failed" || status === "unavailable" ? (
        <p className="text-sm text-rose-700">{message}</p>
      ) : (
        <p className="text-sm text-teal-900/70">
          Follow the pictures in order. The highlighted one matches the part we are reading.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {scenes.map((scene, i) => (
          <div
            key={scene.id}
            className={`overflow-hidden rounded-2xl border-4 ${
              i === index ? "border-amber-500 shadow-md" : "border-transparent"
            }`}
          >
            <button
              type="button"
              onClick={() => setPicked(i)}
              className="block w-full text-left"
            >
              {urls[scene.id] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={urls[scene.id]} alt={scene.caption} className="h-28 w-full object-cover" />
              ) : (
                <div className="flex h-28 items-center justify-center bg-teal-50 text-teal-800/60">
                  <ImageIcon className="h-6 w-6" />
                </div>
              )}
              <p className="bg-white px-2 py-1 text-[11px] font-semibold text-teal-900">
                {i + 1}. {scene.caption.slice(0, 48)}
                {scene.caption.length > 48 ? "…" : ""}
              </p>
            </button>
            {urls[scene.id] ? (
              <Button
                size="sm"
                variant="ghost"
                className="w-full rounded-none border-t border-teal-900/10"
                onClick={() => downloadSceneImage(urls[scene.id], `story-scene-${i + 1}.png`)}
              >
                <Download className="h-3.5 w-3.5" />
                Save
              </Button>
            ) : null}
          </div>
        ))}
      </div>
      <Button size="sm" variant="ghost" disabled={drawing} onClick={redraw}>
        {drawing ? "Drawing the next pictures..." : "Redraw pictures"}
      </Button>
    </Card>
  );
}
