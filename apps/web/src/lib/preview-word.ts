import {
  elevenLabsVoiceId,
  fetchElevenLabsVoices,
  playElevenLabsSpeech,
} from "@/lib/elevenlabs";
import {
  buildUtterance,
  cancelSpeech,
  hasNativeVoice,
  speakableWord,
  waitForVoices,
} from "@/lib/speech";

let hoverTimer: number | null = null;
let previewRun = 0;

export function clearHoverTimer() {
  if (hoverTimer != null) {
    window.clearTimeout(hoverTimer);
    hoverTimer = null;
  }
}

export function cancelWordPreview() {
  clearHoverTimer();
  previewRun += 1;
  cancelSpeech();
}

export async function previewWord(opts: {
  text: string;
  language: string;
  volume: number;
  preferredVoiceURI: string | null;
}) {
  const word = speakableWord(opts.text);
  if (!word) return;
  const run = ++previewRun;
  let elevenId = elevenLabsVoiceId(opts.preferredVoiceURI);
  if (!elevenId && opts.language === "mr") {
    const voices = await waitForVoices();
    if (run !== previewRun) return;
    if (!hasNativeVoice("mr", voices)) {
      const result = await fetchElevenLabsVoices();
      if (run !== previewRun) return;
      elevenId = result.voices[0]?.id || "default";
    }
  }
  if (elevenId) {
    try {
      await playElevenLabsSpeech({
        text: word,
        voiceId: elevenId,
        speed: "slow",
        language: opts.language,
        volume: opts.volume,
        isCancelled: () => run !== previewRun,
      });
    } catch {
      /* Hover preview is best-effort. */
    }
    return;
  }
  cancelSpeech();
  const voices = await waitForVoices();
  if (run !== previewRun) return;
  if (opts.language === "mr" && !hasNativeVoice("mr", voices)) return;
  const { utterance } = buildUtterance(word, {
    language: opts.language,
    speed: "slow",
    volume: opts.volume,
    voices,
    preferredVoiceURI: opts.preferredVoiceURI,
    keepAlive: false,
  });
  window.speechSynthesis.speak(utterance);
}

export function scheduleWordPreview(
  opts: {
    text: string;
    language: string;
    volume: number;
    preferredVoiceURI: string | null;
  },
  delayMs?: number,
) {
  clearHoverTimer();
  const wait = delayMs ?? (elevenLabsVoiceId(opts.preferredVoiceURI) ? 650 : 400);
  hoverTimer = window.setTimeout(() => {
    hoverTimer = null;
    void previewWord(opts);
  }, wait);
}
