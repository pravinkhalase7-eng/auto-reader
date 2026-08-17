import { api, apiAudio } from "@/lib/api";
import type { SpeechSpeed } from "@/lib/speech";

export const ELEVENLABS_PREFIX = "elevenlabs:";

const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";

export type ElevenLabsVoice = {
  id: string;
  name: string;
  accent?: string;
  category?: string;
};

type SpeakOpts = {
  text: string;
  voiceId: string;
  speed: SpeechSpeed;
  language: string;
};

let currentAudio: HTMLAudioElement | null = null;
let finishCurrent: ((result: "ended" | "interrupted" | "error") => void) | null = null;

/** In-memory blob cache — avoids re-calling ElevenLabs for the same line. */
const audioCache = new Map<string, Blob>();
const inflight = new Map<string, Promise<Blob>>();
const MAX_CACHE = 48;

export function isElevenLabsVoice(uri: string | null | undefined): boolean {
  return Boolean(uri?.startsWith(ELEVENLABS_PREFIX));
}

export function elevenLabsVoiceId(uri: string | null | undefined): string | null {
  if (!isElevenLabsVoice(uri) || !uri) return null;
  return uri.slice(ELEVENLABS_PREFIX.length) || null;
}

export function elevenLabsVoiceURI(id: string) {
  return `${ELEVENLABS_PREFIX}${id}`;
}

function cacheKey(opts: SpeakOpts) {
  return [opts.voiceId, opts.speed, opts.language, opts.text.trim()].join("\u0001");
}

function remember(key: string, blob: Blob) {
  if (audioCache.has(key)) audioCache.delete(key);
  audioCache.set(key, blob);
  while (audioCache.size > MAX_CACHE) {
    const oldest = audioCache.keys().next().value;
    if (oldest === undefined) break;
    audioCache.delete(oldest);
  }
}

function enableInlinePlayback(audio: HTMLAudioElement) {
  audio.setAttribute("playsinline", "true");
}

function getPlaybackAudio() {
  if (typeof window === "undefined") return null;
  if (!currentAudio) {
    currentAudio = new Audio();
    enableInlinePlayback(currentAudio);
    currentAudio.preload = "auto";
  }
  return currentAudio;
}

/** Call from a click handler so later blob playback is allowed. */
export function primeElevenLabsPlayback() {
  if (typeof window === "undefined") return;
  const ping = new Audio(SILENT_WAV);
  ping.muted = true;
  enableInlinePlayback(ping);
  void ping.play().catch(() => undefined);
  const audio = getPlaybackAudio();
  if (!audio || (!audio.paused && audio.src.startsWith("blob:"))) return;
  audio.muted = true;
  audio.src = SILENT_WAV;
  void audio
    .play()
    .catch(() => undefined)
    .finally(() => {
      if (audio.src.startsWith("blob:")) return;
      audio.pause();
      audio.muted = false;
    });
}

export function cancelElevenLabsAudio() {
  const finish = finishCurrent;
  finishCurrent = null;
  if (currentAudio) {
    currentAudio.onended = null;
    currentAudio.onerror = null;
    currentAudio.ontimeupdate = null;
    currentAudio.oncanplay = null;
    currentAudio.onloadedmetadata = null;
    currentAudio.pause();
    currentAudio.removeAttribute("src");
    currentAudio.load();
  }
  finish?.("interrupted");
}

export function clearElevenLabsCache() {
  audioCache.clear();
  inflight.clear();
}

export async function fetchElevenLabsVoices(): Promise<{ enabled: boolean; voices: ElevenLabsVoice[] }> {
  try {
    const data = await api<{ elevenlabs: boolean; voices: ElevenLabsVoice[] }>("/tts/voices");
    const voices = data.voices || [];
    return { enabled: Boolean(data.elevenlabs || voices.length), voices };
  } catch {
    return { enabled: false, voices: [] };
  }
}

export async function fetchElevenLabsAudio(opts: SpeakOpts): Promise<Blob> {
  const key = cacheKey(opts);
  const hit = audioCache.get(key);
  if (hit) return hit;

  const pending = inflight.get(key);
  if (pending) return pending;

  const request = apiAudio("/tts/speak", {
    text: opts.text,
    voice_id: opts.voiceId,
    speed: opts.speed,
    language: opts.language,
  })
    .then((blob) => {
      remember(key, blob);
      return blob;
    })
    .finally(() => {
      inflight.delete(key);
    });

  inflight.set(key, request);
  return request;
}

/** Warm the next line while the current one plays — removes inter-sentence buffering. */
export function prefetchElevenLabsAudio(opts: SpeakOpts) {
  const key = cacheKey(opts);
  if (audioCache.has(key) || inflight.has(key)) return;
  void fetchElevenLabsAudio(opts).catch(() => undefined);
}

function durationMs(audio: HTMLAudioElement, text: string) {
  if (Number.isFinite(audio.duration) && audio.duration > 0) return audio.duration * 1000;
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(700, words * 380);
}

export async function playElevenLabsSpeech(opts: {
  text: string;
  voiceId: string;
  speed: SpeechSpeed;
  language: string;
  volume: number;
  onStart?: () => void;
  onProgress?: (elapsedMs: number, durationMs: number) => void;
  isCancelled?: () => boolean;
}): Promise<"ended" | "interrupted" | "error"> {
  cancelElevenLabsAudio();

  // Fetch (or reuse cache) before wiring audio — prefetch makes this near-instant mid-lesson
  const blob = await fetchElevenLabsAudio({
    text: opts.text,
    voiceId: opts.voiceId,
    speed: opts.speed,
    language: opts.language,
  });
  if (opts.isCancelled?.()) return "interrupted";

  const audio = getPlaybackAudio();
  if (!audio) return "error";
  const url = URL.createObjectURL(blob);
  audio.volume = Math.min(1, Math.max(0, opts.volume));

  return new Promise((resolve) => {
    let raf = 0;
    let settled = false;
    const finish = (result: "ended" | "interrupted" | "error") => {
      if (settled) return;
      settled = true;
      if (finishCurrent === finish) finishCurrent = null;
      window.cancelAnimationFrame(raf);
      audio.onended = null;
      audio.onerror = null;
      audio.ontimeupdate = null;
      audio.oncanplay = null;
      audio.onloadedmetadata = null;
      URL.revokeObjectURL(url);
      resolve(result);
    };
    finishCurrent = finish;
    const emitProgress = () => {
      opts.onProgress?.(audio.currentTime * 1000, durationMs(audio, opts.text));
    };
    const tick = () => {
      if (opts.isCancelled?.()) {
        cancelElevenLabsAudio();
        finish("interrupted");
        return;
      }
      emitProgress();
      if (!audio.paused && !audio.ended) raf = window.requestAnimationFrame(tick);
    };
    audio.onended = () => finish(opts.isCancelled?.() ? "interrupted" : "ended");
    audio.onerror = () => finish("error");
    audio.ontimeupdate = () => emitProgress();

    let begun = false;
    const start = () => {
      if (settled || begun) return;
      begun = true;
      if (opts.isCancelled?.()) {
        finish("interrupted");
        return;
      }
      opts.onStart?.();
      emitProgress();
      audio
        .play()
        .then(() => {
          raf = window.requestAnimationFrame(tick);
        })
        .catch(() => finish("error"));
    };

    // Start as soon as the blob can play — no artificial 400ms wait
    audio.onloadedmetadata = () => start();
    audio.oncanplay = () => start();
    audio.src = url;
    audio.load();
    // Tiny fallback if metadata events are delayed on some browsers
    window.setTimeout(start, 80);
  });
}
