"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Film, Pause, Play, Square, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
  recorderMimeType,
  sceneIndexForParagraph,
  storyNarration,
  wrapCaption,
} from "@/lib/story-video";
import {
  buildUtterance,
  cancelSpeech,
  waitForVoices,
} from "@/lib/speech";
import { useReaderStore } from "@/store/reader-store";
import type { LessonContent, StoryIllustration } from "@/types";

type Props = {
  title: string;
  content: LessonContent;
  scenes: StoryIllustration[];
  urls: Record<string, string>;
};

function coverImage(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement,
  zoom: number,
) {
  const scale = Math.max(VIDEO_WIDTH / image.naturalWidth, VIDEO_HEIGHT / image.naturalHeight) * zoom;
  const dw = image.naturalWidth * scale;
  const dh = image.naturalHeight * scale;
  ctx.drawImage(image, (VIDEO_WIDTH - dw) / 2, (VIDEO_HEIGHT - dh) / 2, dw, dh);
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  opts: {
    image?: HTMLImageElement;
    title: string;
    caption: string;
    spoken: string;
    zoom: number;
  },
) {
  ctx.fillStyle = "#042f2e";
  ctx.fillRect(0, 0, VIDEO_WIDTH, VIDEO_HEIGHT);
  if (opts.image) {
    coverImage(ctx, opts.image, opts.zoom);
  }
  const barH = 168;
  ctx.fillStyle = "rgba(4, 47, 46, 0.78)";
  ctx.fillRect(0, VIDEO_HEIGHT - barH, VIDEO_WIDTH, barH);
  ctx.fillStyle = "#fde68a";
  ctx.font = "600 28px Nunito, Nirmala UI, Noto Sans Devanagari, sans-serif";
  ctx.fillText(opts.title.slice(0, 64), 36, VIDEO_HEIGHT - 128);
  ctx.fillStyle = "#ffffff";
  ctx.font = "600 30px Nunito, Nirmala UI, Noto Sans Devanagari, sans-serif";
  const lines = wrapCaption(opts.spoken || opts.caption, 62, 3);
  lines.forEach((line, i) => {
    ctx.fillText(line, 36, VIDEO_HEIGHT - 84 + i * 36);
  });
}

async function loadImage(url: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}

export function StoryVideo({ title, content, scenes, urls }: Props) {
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("Pictures on screen, story read aloud.");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stopRef = useRef(false);
  const pausedRef = useRef(false);
  const runIdRef = useRef(0);
  const imagesRef = useRef<HTMLImageElement[]>([]);
  const spokenRef = useRef("");
  const sceneIndexRef = useRef(0);
  const startedAtRef = useRef(0);
  const preferredVoiceURI = useReaderStore((s) => s.preferredVoiceURI);
  const volume = useReaderStore((s) => s.volume);
  const speed = useReaderStore((s) => s.speed);
  const setReaderPlaying = useReaderStore((s) => s.setPlaying);

  const paragraphs = useMemo(() => storyNarration(content), [content]);
  const canPlay = scenes.length > 0 && paragraphs.length > 0 && scenes.every((scene) => urls[scene.id]);

  useEffect(() => {
    if (!open) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    const tick = () => {
      const scene = scenes[sceneIndexRef.current] ?? scenes[0];
      const elapsed = (performance.now() - startedAtRef.current) / 8000;
      const zoom = 1 + 0.08 * (0.5 + 0.5 * Math.sin(elapsed));
      drawFrame(ctx, {
        image: imagesRef.current[sceneIndexRef.current] ?? imagesRef.current[0],
        title,
        caption: scene?.caption ?? "",
        spoken: spokenRef.current,
        zoom,
      });
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [open, scenes, title]);

  useEffect(() => {
    if (!open) return;
    void Promise.all(
      scenes.map((scene) => (urls[scene.id] ? loadImage(urls[scene.id]) : Promise.resolve(null))),
    ).then((images) => {
      imagesRef.current = images.filter((image): image is HTMLImageElement => !!image);
      sceneIndexRef.current = 0;
      spokenRef.current = paragraphs[0] || scenes[0]?.caption || "";
    });
  }, [open, paragraphs, scenes, urls]);

  useEffect(() => {
    if (open) return;
    stopRef.current = true;
    cancelSpeech();
    setPlaying(false);
    setSaving(false);
  }, [open]);

  async function speakChunk(text: string, runId: number) {
    const voices = await waitForVoices();
    return new Promise<"ended" | "stopped">((resolve) => {
      const { utterance } = buildUtterance(text, {
        language: content.language,
        speed,
        volume,
        voices,
        preferredVoiceURI,
        keepAlive: true,
      });
      utterance.onend = () => resolve(stopRef.current || runIdRef.current !== runId ? "stopped" : "ended");
      utterance.onerror = () => resolve("stopped");
      window.speechSynthesis.speak(utterance);
    });
  }

  async function runShow(record: boolean) {
    if (!canPlay || !canvasRef.current) return;
    const runId = ++runIdRef.current;
    stopRef.current = false;
    pausedRef.current = false;
    setReaderPlaying(false);
    cancelSpeech();
    setPlaying(true);
    setSaving(record);
    setStatus(record ? "Saving the story video..." : "Playing the story video...");
    startedAtRef.current = performance.now();

    imagesRef.current = await Promise.all(scenes.map((scene) => loadImage(urls[scene.id])));
    if (stopRef.current || runIdRef.current !== runId) return;

    let recorder: MediaRecorder | null = null;
    const chunks: BlobPart[] = [];
    if (record) {
      const mime = recorderMimeType();
      if (mime == null) {
        setStatus("This browser cannot save video. Play it here instead.");
        setSaving(false);
        setPlaying(false);
        return;
      }
      const stream = canvasRef.current.captureStream(30);
      recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recorder.start(250);
    }

    for (let i = 0; i < paragraphs.length; i++) {
      if (stopRef.current || runIdRef.current !== runId) break;
      while (pausedRef.current && !stopRef.current && runIdRef.current === runId) {
        await new Promise((r) => window.setTimeout(r, 80));
      }
      if (stopRef.current || runIdRef.current !== runId) break;
      sceneIndexRef.current = Math.max(
        0,
        sceneIndexForParagraph(i, paragraphs.length, scenes.length),
      );
      spokenRef.current = paragraphs[i];
      const result = await speakChunk(paragraphs[i], runId);
      if (result === "stopped") break;
    }

    if (recorder && recorder.state !== "inactive") {
      await new Promise<void>((resolve) => {
        recorder.onstop = () => resolve();
        recorder.stop();
      });
      if (chunks.length && !stopRef.current) {
        const blob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${title.replace(/[^\w]+/g, "-").slice(0, 40) || "story"}-video.webm`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 4000);
      }
    }

    if (runIdRef.current === runId) {
      cancelSpeech();
      setPlaying(false);
      setSaving(false);
      setStatus(record ? "Video saved. Play it again any time." : "Story finished. Play again whenever you like.");
    }
  }

  function stopShow() {
    stopRef.current = true;
    pausedRef.current = false;
    runIdRef.current += 1;
    cancelSpeech();
    setPlaying(false);
    setSaving(false);
    setStatus("Stopped.");
  }

  function togglePause() {
    if (!playing) return;
    pausedRef.current = !pausedRef.current;
    if (pausedRef.current) {
      window.speechSynthesis.pause();
      setStatus("Paused.");
    } else {
      window.speechSynthesis.resume();
      setStatus("Playing the story video...");
    }
  }

  if (!canPlay) return null;

  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        <Film className="h-3.5 w-3.5" />
        Story video
      </Button>
      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-teal-950/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Story video"
        >
          <div className="w-full max-w-4xl rounded-3xl bg-white p-4 shadow-xl">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="font-display text-xl font-semibold text-teal-950">Story video</p>
                <p className="text-sm text-teal-900/70">{status}</p>
              </div>
              <Button variant="ghost" onClick={() => { stopShow(); setOpen(false); }}>
                Close
              </Button>
            </div>
            <canvas
              ref={canvasRef}
              width={VIDEO_WIDTH}
              height={VIDEO_HEIGHT}
              className="w-full rounded-2xl bg-teal-950"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button disabled={playing} onClick={() => void runShow(false)}>
                <Play className="h-4 w-4" />
                Play with voice
              </Button>
              <Button variant="outline" disabled={!playing} onClick={togglePause}>
                <Pause className="h-4 w-4" />
                Pause
              </Button>
              <Button variant="outline" disabled={!playing && !saving} onClick={stopShow}>
                <Square className="h-4 w-4" />
                Stop
              </Button>
              <Button
                variant="secondary"
                disabled={playing || saving || recorderMimeType() == null}
                onClick={() => void runShow(true)}
              >
                <Download className="h-4 w-4" />
                {saving ? "Saving video..." : "Save video"}
              </Button>
            </div>
            <p className="mt-2 text-xs text-teal-900/60">
              Play reads the story aloud over the pictures. Save downloads the picture video with
              the story words on screen (browsers cannot put speech-synthesis audio into the file).
            </p>
          </div>
        </div>
      ) : null}
    </>
  );
}
