"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Film, Pause, Play, Square, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  VIDEO_ASPECTS,
  recorderMimeType,
  sceneIndexForParagraph,
  sceneMediaUrl,
  storyNarration,
  videoDimensions,
  type VideoAspect,
} from "@/lib/story-video";
import {
  elevenLabsVoiceId,
  fetchElevenLabsAudio,
  fetchElevenLabsVoices,
  playElevenLabsSpeech,
  primeElevenLabsPlayback,
} from "@/lib/elevenlabs";
import {
  buildUtterance,
  cancelSpeech,
  hasNativeVoice,
  waitForVoices,
} from "@/lib/speech";
import { convertVideoToMp4, looksLikeMp4 } from "@/lib/video-export";
import { useReaderStore } from "@/store/reader-store";
import { cn } from "@/lib/utils";
import type { LessonContent, StoryIllustration } from "@/types";

type Props = {
  title: string;
  content: LessonContent;
  scenes: StoryIllustration[];
  urls: Record<string, string>;
  portraitUrls?: Record<string, string>;
};

type AudioGraph = {
  ctx: AudioContext;
  dest: MediaStreamAudioDestinationNode;
  gain: GainNode;
  source: AudioBufferSourceNode | null;
  closed: boolean;
};

type MotionState = {
  sceneIndex: number;
  prevSceneIndex: number;
  transitionAt: number;
  clipStartedAt: number;
  active: boolean;
};

function easeInOut(t: number) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function coverImage(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement,
  width: number,
  height: number,
  zoom: number,
  panX: number,
  panY: number,
) {
  const base = Math.max(width / image.naturalWidth, height / image.naturalHeight);
  const scale = base * zoom;
  const dw = image.naturalWidth * scale;
  const dh = image.naturalHeight * scale;
  const maxX = Math.max(0, (dw - width) / 2);
  const maxY = Math.max(0, (dh - height) / 2);
  const dx = (width - dw) / 2 + panX * maxX;
  const dy = (height - dh) / 2 + panY * maxY;
  ctx.drawImage(image, dx, dy, dw, dh);
}

/** Slow cinematic drift only — no per-frame sway (that looked like shaking). */
function kenBurnsForScene(sceneIndex: number, elapsedSec: number) {
  // ~14s to finish a gentle move; ease so speed stays even
  const drift = easeInOut(Math.min(1, elapsedSec / 14));
  const zoom = 1.06 + drift * 0.1;
  const pattern = sceneIndex % 4;
  switch (pattern) {
    case 0:
      return { zoom, panX: -0.35 + drift * 0.7, panY: -0.15 + drift * 0.25 };
    case 1:
      return { zoom, panX: 0.35 - drift * 0.7, panY: 0.12 - drift * 0.2 };
    case 2:
      return { zoom: zoom + 0.02, panX: -0.08 + drift * 0.16, panY: -0.3 + drift * 0.55 };
    default:
      return { zoom: zoom + 0.01, panX: 0.1 - drift * 0.2, panY: 0.25 - drift * 0.45 };
  }
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  opts: {
    image?: HTMLImageElement;
    prevImage?: HTMLImageElement | null;
    aspect: VideoAspect;
    sceneIndex: number;
    elapsedMs: number;
    transitionAt: number;
  },
) {
  const { width, height } = videoDimensions(opts.aspect);
  ctx.fillStyle = "#042f2e";
  ctx.fillRect(0, 0, width, height);

  const now = performance.now();
  const transitionMs = 900;
  const t = opts.prevImage
    ? easeInOut(Math.min(1, Math.max(0, (now - opts.transitionAt) / transitionMs)))
    : 1;
  const elapsedSec = Math.max(0, opts.elapsedMs / 1000);
  const motion = kenBurnsForScene(opts.sceneIndex, elapsedSec);

  if (opts.prevImage && t < 1) {
    // Keep previous scene frozen at its end pose so crossfade doesn't jitter
    const prevMotion = kenBurnsForScene(Math.max(0, opts.sceneIndex - 1), 14);
    ctx.save();
    ctx.globalAlpha = 1 - t;
    coverImage(ctx, opts.prevImage, width, height, prevMotion.zoom, prevMotion.panX, prevMotion.panY);
    ctx.restore();
  }

  if (opts.image) {
    ctx.save();
    ctx.globalAlpha = opts.prevImage && t < 1 ? t : 1;
    coverImage(ctx, opts.image, width, height, motion.zoom, motion.panX, motion.panY);
    ctx.restore();
  }

  const gradient = ctx.createRadialGradient(
    width / 2,
    height / 2,
    Math.min(width, height) * 0.42,
    width / 2,
    height / 2,
    Math.max(width, height) * 0.78,
  );
  gradient.addColorStop(0, "rgba(0,0,0,0)");
  gradient.addColorStop(1, "rgba(4,47,46,0.22)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
}

async function loadImage(url: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}

function audioState(ctx: AudioContext): string {
  return ctx.state as string;
}

function isAudioClosed(ctx: AudioContext): boolean {
  return audioState(ctx) === "closed";
}

function createAudioGraph(volume: number): AudioGraph {
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new Ctor();
  const dest = ctx.createMediaStreamDestination();
  const gain = ctx.createGain();
  gain.gain.value = Math.min(1, Math.max(0, volume));
  gain.connect(ctx.destination);
  gain.connect(dest);
  const silence = ctx.createConstantSource();
  silence.offset.value = 0;
  silence.connect(dest);
  silence.start();
  return {
    ctx,
    dest,
    gain,
    source: null,
    closed: false,
  };
}

async function playThroughGraph(
  graph: AudioGraph,
  blob: Blob,
  isCancelled: () => boolean,
): Promise<"ended" | "stopped"> {
  if (graph.closed || isAudioClosed(graph.ctx)) return "stopped";
  const data = (await blob.arrayBuffer()).slice(0);
  if (graph.closed || isAudioClosed(graph.ctx) || isCancelled()) return "stopped";
  const buffer = await graph.ctx.decodeAudioData(data);
  if (graph.closed || isAudioClosed(graph.ctx) || isCancelled()) return "stopped";
  if (graph.ctx.state === "suspended") await graph.ctx.resume();
  const src = graph.ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(graph.gain);
  graph.source = src;
  return new Promise((resolve) => {
    let settled = false;
    const finish = (result: "ended" | "stopped") => {
      if (settled) return;
      settled = true;
      window.clearInterval(poll);
      if (graph.source === src) graph.source = null;
      resolve(result);
    };
    const poll = window.setInterval(() => {
      if (isCancelled()) {
        try {
          src.stop();
        } catch {
          /* already stopped */
        }
        finish("stopped");
      }
    }, 80);
    src.onended = () => finish(isCancelled() ? "stopped" : "ended");
    src.start();
  });
}

function startRecorder(canvas: HTMLCanvasElement, audio: MediaStream) {
  const videoTracks = canvas.captureStream(30).getVideoTracks();
  const audioTracks = audio.getAudioTracks();
  if (!videoTracks.length) {
    throw new Error("This browser could not capture the story pictures.");
  }
  if (!audioTracks.length) {
    throw new Error("This browser could not capture the story voice.");
  }
  audioTracks.forEach((track) => {
    track.enabled = true;
  });
  const mixed = new MediaStream([...videoTracks, ...audioTracks]);
  const types = [
    "video/webm;codecs=vp8,opus",
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,pcm",
    "video/webm",
    "video/mp4",
    "",
  ];
  for (const mime of types) {
    if (mime && !MediaRecorder.isTypeSupported(mime)) continue;
    try {
      const options: MediaRecorderOptions = {
        audioBitsPerSecond: 128_000,
        videoBitsPerSecond: 2_500_000,
      };
      if (mime) options.mimeType = mime;
      const recorder = new MediaRecorder(mixed, options);
      recorder.start(250);
      return recorder;
    } catch {
      /* try the next mime type */
    }
  }
  throw new Error("This browser could not start video recording.");
}

function fileSlug(title: string) {
  const ascii = title.replace(/[^\w]+/g, "-").replace(/^-+|-+$/g, "");
  return ascii.slice(0, 40) || "story";
}

function offerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  return url;
}

function closeAudioGraph(graph: AudioGraph | null) {
  if (!graph || graph.closed) return;
  graph.closed = true;
  try {
    graph.source?.stop();
  } catch {
    /* already stopped */
  }
  graph.source = null;
  try {
    if (!isAudioClosed(graph.ctx)) {
      void graph.ctx.close().catch(() => undefined);
    }
  } catch {
    /* already closed */
  }
}

export function StoryVideo({ title, content, scenes, urls, portraitUrls = {} }: Props) {
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveProgress, setSaveProgress] = useState(0);
  const [aspect, setAspect] = useState<VideoAspect>("16:9");
  const [status, setStatus] = useState("Pictures on screen, story read aloud.");
  const [readyFile, setReadyFile] = useState<{ url: string; name: string } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stopRef = useRef(false);
  const pausedRef = useRef(false);
  const runIdRef = useRef(0);
  const imagesRef = useRef<HTMLImageElement[]>([]);
  const sceneIndexRef = useRef(0);
  const startedAtRef = useRef(0);
  const aspectRef = useRef<VideoAspect>(aspect);
  const graphRef = useRef<AudioGraph | null>(null);
  const motionRef = useRef<MotionState>({
    sceneIndex: 0,
    prevSceneIndex: -1,
    transitionAt: 0,
    clipStartedAt: 0,
    active: false,
  });
  const preferredVoiceURI = useReaderStore((s) => s.preferredVoiceURI);
  const volume = useReaderStore((s) => s.volume);
  const speed = useReaderStore((s) => s.speed);
  const setReaderPlaying = useReaderStore((s) => s.setPlaying);

  const paragraphs = useMemo(() => storyNarration(content), [content]);
  const canPlay = scenes.length > 0 && paragraphs.length > 0 && scenes.every((scene) => urls[scene.id]);
  const portraitsReady = scenes.every((scene) => !!portraitUrls[scene.id]);
  const size = videoDimensions(aspect);
  aspectRef.current = aspect;

  const setSceneAnimated = (next: number) => {
    const motion = motionRef.current;
    if (next === motion.sceneIndex) return;
    motion.prevSceneIndex = motion.sceneIndex;
    motion.sceneIndex = next;
    motion.transitionAt = performance.now();
    motion.clipStartedAt = performance.now();
    sceneIndexRef.current = next;
  };

  useEffect(() => {
    if (!open) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    canvas.width = size.width;
    canvas.height = size.height;
    let raf = 0;
    const tick = () => {
      const motion = motionRef.current;
      const images = imagesRef.current;
      const current = images[motion.sceneIndex] ?? images[0];
      const prev =
        motion.prevSceneIndex >= 0 && performance.now() - motion.transitionAt < 950
          ? images[motion.prevSceneIndex]
          : null;
      drawFrame(ctx, {
        image: current,
        prevImage: prev,
        aspect: aspectRef.current,
        sceneIndex: motion.sceneIndex,
        elapsedMs: motion.clipStartedAt ? performance.now() - motion.clipStartedAt : 0,
        transitionAt: motion.transitionAt,
      });
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [open, scenes, size.height, size.width]);

  useEffect(() => {
    if (!open) return;
    void Promise.all(
      scenes.map((scene) => {
        const url = sceneMediaUrl(scene.id, aspect, urls, portraitUrls);
        return url ? loadImage(url) : Promise.resolve(null);
      }),
    ).then((images) => {
      imagesRef.current = images.filter((image): image is HTMLImageElement => !!image);
      sceneIndexRef.current = 0;
      motionRef.current.sceneIndex = 0;
      motionRef.current.prevSceneIndex = -1;
      motionRef.current.clipStartedAt = performance.now();
    });
  }, [aspect, open, portraitUrls, scenes, urls]);

  useEffect(() => {
    if (open) return;
    stopRef.current = true;
    cancelSpeech();
    closeAudioGraph(graphRef.current);
    graphRef.current = null;
    setPlaying(false);
    setSaving(false);
    setSaveProgress(0);
    setReadyFile((prev) => {
      if (prev) URL.revokeObjectURL(prev.url);
      return null;
    });
  }, [open]);

  async function speakChunk(text: string, runId: number) {
    const elevenId = elevenLabsVoiceId(preferredVoiceURI);
    if (elevenId) {
      try {
        const result = await playElevenLabsSpeech({
          text,
          voiceId: elevenId,
          speed,
          language: content.language,
          volume,
          isCancelled: () => stopRef.current || runIdRef.current !== runId,
        });
        return result === "ended" && !stopRef.current && runIdRef.current === runId ? "ended" : "stopped";
      } catch {
        if (content.language === "mr") {
          setStatus("Could not play a Marathi voice for this line.");
          return "stopped";
        }
        setStatus("ElevenLabs could not speak this line. Using this device instead.");
      }
    }
    const voices = await waitForVoices();
    if (content.language === "mr" && !hasNativeVoice("mr", voices)) {
      setStatus("This device has no Marathi voice, so Hindi will not be used.");
      return "stopped";
    }
    return new Promise<"ended" | "stopped">((resolve) => {
      const { utterance } = buildUtterance(text, {
        language: content.language,
        speed,
        volume,
        voices,
        preferredVoiceURI: elevenId ? null : preferredVoiceURI,
        keepAlive: true,
      });
      utterance.onend = () => resolve(stopRef.current || runIdRef.current !== runId ? "stopped" : "ended");
      utterance.onerror = () => resolve("stopped");
      window.speechSynthesis.speak(utterance);
    });
  }

  async function resolveSaveVoice(): Promise<{ id: string; name: string } | null> {
    const selected = elevenLabsVoiceId(preferredVoiceURI);
    const { enabled, voices } = await fetchElevenLabsVoices();
    if (!enabled || !voices.length) return null;
    const match = selected ? voices.find((voice) => voice.id === selected) : undefined;
    const voice = match || voices[0];
    return { id: voice.id, name: voice.name };
  }

  async function runShow(record: boolean) {
    if (!canPlay || !canvasRef.current) return;
    primeElevenLabsPlayback();
    const runId = ++runIdRef.current;
    stopRef.current = false;
    pausedRef.current = false;
    setReaderPlaying(false);
    cancelSpeech();
    setPlaying(true);
    setSaving(record);
    setSaveProgress(record ? 1 : 0);
    setStatus(record ? "Preparing the story voice..." : "Playing the story video...");
    startedAtRef.current = performance.now();
    motionRef.current.active = true;
    motionRef.current.clipStartedAt = performance.now();

    let recorder: MediaRecorder | null = null;
    const chunks: BlobPart[] = [];
    let graph: AudioGraph | null = null;
    let clips: Blob[] | null = null;
    let voiceName = "";
    let savedOk = false;

    if (record) {
      closeAudioGraph(graphRef.current);
      try {
        graph = createAudioGraph(volume);
        graphRef.current = graph;
        void graph.ctx.resume();
      } catch {
        setStatus("This browser could not open an audio recorder. Try Chrome or Edge.");
        setSaving(false);
        setPlaying(false);
        setSaveProgress(0);
        return;
      }
    }

    try {
      setSaveProgress(record ? 4 : 0);
      imagesRef.current = await Promise.all(
        scenes.map((scene) => loadImage(sceneMediaUrl(scene.id, aspect, urls, portraitUrls))),
      );
      if (stopRef.current || runIdRef.current !== runId) return;

      if (record) {
        if (recorderMimeType() == null) {
          setStatus("This browser cannot save video. Play it here instead.");
          return;
        }
        const voice = await resolveSaveVoice();
        if (!voice) {
          setStatus(
            "Pick an ElevenLabs voice in the player, then save. This device's voice cannot go into the video file.",
          );
          return;
        }
        voiceName = voice.name;
        const selectedId = elevenLabsVoiceId(preferredVoiceURI);
        setStatus(
          selectedId && selectedId === voice.id
            ? `Preparing voice (${voice.name}) for ${aspect} video...`
            : `This device's voice cannot be saved. Preparing ${voice.name} for ${aspect} video...`,
        );
        clips = [];
        for (let i = 0; i < paragraphs.length; i++) {
          if (stopRef.current || runIdRef.current !== runId) return;
          const preparePct = 8 + Math.round(((i + 1) / paragraphs.length) * 32);
          setSaveProgress(preparePct);
          setStatus(`Preparing voice ${i + 1}/${paragraphs.length} · ${preparePct}%`);
          try {
            clips.push(
              await fetchElevenLabsAudio({
                text: paragraphs[i],
                voiceId: voice.id,
                speed,
                language: content.language,
              }),
            );
          } catch {
            setStatus("I couldn't record the selected voice. Try another ElevenLabs voice, then save again.");
            return;
          }
        }
        if (stopRef.current || runIdRef.current !== runId) return;
        if (!graph) {
          setStatus("This browser could not open an audio recorder. Try Chrome or Edge.");
          return;
        }
        if (audioState(graph.ctx) === "suspended") await graph.ctx.resume();
        setSaveProgress(42);
        try {
          recorder = startRecorder(canvasRef.current, graph.dest.stream);
        } catch (err) {
          setStatus(err instanceof Error ? err.message : "Could not start saving the video.");
          return;
        }
        recorder.ondataavailable = (event) => {
          if (event.data.size) chunks.push(event.data);
        };
        // Let the MediaStream settle so the first audio samples are not dropped.
        await new Promise((r) => window.setTimeout(r, 350));
        if (audioState(graph.ctx) === "suspended") await graph.ctx.resume();
        setStatus(`Saving ${aspect} video with ${voice.name} (with audio)...`);
        setSaveProgress(45);
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
        setSceneAnimated(sceneIndexRef.current);
        motionRef.current.clipStartedAt = performance.now();
        if (record) {
          const playPct = 45 + Math.round(((i + 0.5) / paragraphs.length) * 42);
          setSaveProgress(Math.min(88, playPct));
          setStatus(
            `Saving video with audio · scene ${i + 1}/${paragraphs.length} · ${Math.min(88, playPct)}%`,
          );
        }
        const result =
          record && graph && clips
            ? await playThroughGraph(graph, clips[i], () => stopRef.current || runIdRef.current !== runId)
            : await speakChunk(paragraphs[i], runId);
        if (result === "stopped") break;
        if (record) {
          const donePct = 45 + Math.round(((i + 1) / paragraphs.length) * 42);
          setSaveProgress(Math.min(88, donePct));
        }
      }

      if (recorder && recorder.state !== "inactive") {
        const activeRecorder = recorder;
        setSaveProgress(90);
        setStatus(voiceName ? `Finishing video with ${voiceName}...` : "Finishing video...");
        await new Promise((r) => window.setTimeout(r, 500));
        await new Promise<void>((resolve) => {
          activeRecorder.onstop = () => resolve();
          try {
            if (activeRecorder.state === "recording") activeRecorder.requestData();
            activeRecorder.stop();
          } catch {
            resolve();
          }
        });
        if (chunks.length && !stopRef.current) {
          let blob = new Blob(chunks, { type: activeRecorder.mimeType || "video/webm" });
          let name = `${fileSlug(title)}-${aspect.replace(":", "x")}.mp4`;

          if (!looksLikeMp4(blob, activeRecorder.mimeType)) {
            setSaveProgress(91);
            setStatus("Converting to MP4...");
            try {
              const converted = await convertVideoToMp4(blob, {
                isCancelled: () => stopRef.current || runIdRef.current !== runId,
                onProgress: (ratio) => {
                  setSaveProgress(91 + Math.round(ratio * 8));
                },
              });
              blob = converted.blob;
            } catch (err) {
              if (stopRef.current || runIdRef.current !== runId) return;
              name = `${fileSlug(title)}-${aspect.replace(":", "x")}.webm`;
              setStatus(
                err instanceof Error && err.message === "cancelled"
                  ? "Stopped."
                  : "MP4 conversion failed, saving WebM instead.",
              );
            }
          }

          if (stopRef.current || runIdRef.current !== runId) return;
          setSaveProgress(100);
          const url = offerDownload(blob, name);
          setReadyFile((prev) => {
            if (prev) URL.revokeObjectURL(prev.url);
            return { url, name };
          });
          savedOk = true;
          setStatus(
            name.endsWith(".mp4")
              ? "MP4 saved with audio and motion. If the file did not download, tap the link below."
              : "Video saved. If the file did not download, tap the link below.",
          );
        } else if (!stopRef.current) {
          setStatus("The recorder did not produce a file. Try Chrome, then save again.");
        }
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Could not save the story video.");
    } finally {
      motionRef.current.active = false;
      closeAudioGraph(graph);
      if (graphRef.current === graph) graphRef.current = null;
      if (runIdRef.current === runId) {
        cancelSpeech();
        setPlaying(false);
        setSaving(false);
        if (!record) {
          if (!stopRef.current) {
            setStatus("Story finished. Play again whenever you like.");
          }
          setSaveProgress(0);
        } else if (!savedOk) {
          setSaveProgress(0);
        }
      }
    }
  }

  function stopShow() {
    stopRef.current = true;
    pausedRef.current = false;
    runIdRef.current += 1;
    cancelSpeech();
    closeAudioGraph(graphRef.current);
    graphRef.current = null;
    motionRef.current.active = false;
    setPlaying(false);
    setSaving(false);
    setSaveProgress(0);
    setStatus("Stopped.");
  }

  function togglePause() {
    if (!playing) return;
    pausedRef.current = !pausedRef.current;
    const ctx = graphRef.current?.ctx;
    if (ctx && !isAudioClosed(ctx)) {
      if (pausedRef.current) void ctx.suspend().catch(() => undefined);
      else void ctx.resume().catch(() => undefined);
    } else if (pausedRef.current) {
      window.speechSynthesis.pause();
    } else {
      window.speechSynthesis.resume();
    }
    setStatus(
      pausedRef.current
        ? "Paused."
        : saving
          ? `Saving the story video${saveProgress ? ` · ${saveProgress}%` : ""}...`
          : "Playing the story video...",
    );
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
          <div className={cn("w-full rounded-3xl bg-white p-4 shadow-xl", aspect === "9:16" ? "max-w-lg" : "max-w-4xl")}>
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="font-display text-xl font-semibold text-teal-950">Story video</p>
                <p className="text-sm text-teal-900/70">{status}</p>
              </div>
              <Button variant="ghost" onClick={() => { stopShow(); setOpen(false); }}>
                Close
              </Button>
            </div>
            <div className="mb-3 flex flex-wrap gap-2">
              {(Object.keys(VIDEO_ASPECTS) as VideoAspect[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  disabled={playing || saving}
                  onClick={() => setAspect(value)}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-xs font-semibold",
                    aspect === value ? "bg-teal-700 text-white" : "bg-teal-50 text-teal-900",
                  )}
                >
                  {VIDEO_ASPECTS[value].label} · {VIDEO_ASPECTS[value].hint}
                </button>
              ))}
            </div>
            {aspect === "9:16" && !portraitsReady ? (
              <p className="mb-3 text-xs text-teal-900/70">
                Tall 9:16 pictures are still loading. The phone video will use them as soon as they are ready.
              </p>
            ) : null}
            <canvas
              ref={canvasRef}
              width={size.width}
              height={size.height}
              className={cn(
                "rounded-2xl bg-teal-950",
                aspect === "9:16" ? "mx-auto max-h-[58vh] w-auto" : "w-full",
              )}
            />
            {saving || saveProgress > 0 ? (
              <div className="mt-3" aria-live="polite">
                <div className="mb-1 flex items-center justify-between text-xs font-semibold text-teal-900">
                  <span>{saving ? "Saving video with audio" : "Save complete"}</span>
                  <span>{Math.min(100, Math.max(0, saveProgress))}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-teal-100">
                  <div
                    className="h-full rounded-full bg-teal-600 transition-[width] duration-300 ease-out"
                    style={{ width: `${Math.min(100, Math.max(0, saveProgress))}%` }}
                  />
                </div>
              </div>
            ) : null}
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
                {saving ? `Saving ${saveProgress}%` : "Save MP4"}
              </Button>
            </div>
            <p className="mt-2 text-xs text-teal-900/60">
              Pictures slowly zoom and pan like a story film (no shake). Save downloads an MP4
              ({aspect}) with that motion plus the cloud voice. Pick an ElevenLabs voice first —
              this device&apos;s voice cannot be stored in the file.
            </p>
            {readyFile ? (
              <a
                className="mt-2 inline-flex text-sm font-semibold text-teal-800 underline"
                href={readyFile.url}
                download={readyFile.name}
              >
                Video is ready — click to download {readyFile.name}
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
