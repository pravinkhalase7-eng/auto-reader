/** Browser speech helpers — voice picking + rates for student listening. */

export const SPEED_RATE = {
  very_slow: 0.65,
  slow: 0.85,
  normal: 1.05,
} as const;

export type SpeechSpeed = keyof typeof SPEED_RATE;

const LANG_CANDIDATES: Record<string, string[]> = {
  en: ["en-IN", "en-GB", "en-US", "en"],
  hi: ["hi-IN", "hi"],
  // Most desktops lack mr-IN; Hindi voices read Devanagari far better than English.
  mr: ["mr-IN", "mr", "hi-IN", "hi"],
};

function normalize(lang: string) {
  return lang.toLowerCase().replace("_", "-");
}

function scoreVoice(voice: SpeechSynthesisVoice, wanted: string[]): number {
  const vLang = normalize(voice.lang);
  const vName = voice.name.toLowerCase();
  let score = 0;

  wanted.forEach((code, i) => {
    const c = normalize(code);
    if (vLang === c) score += 100 - i * 10;
    else if (vLang.startsWith(c.split("-")[0])) score += 40 - i * 5;
  });

  // Prefer neural / enhanced / natural voices when present
  if (/neural|natural|enhanced|premium|google|microsoft/.test(vName)) score += 15;
  if (voice.localService) score += 5;

  // Strongly avoid English voices for Indic scripts
  const primary = wanted[0]?.split("-")[0];
  if (primary && primary !== "en" && vLang.startsWith("en")) score -= 80;

  return score;
}

export function getVoicesSafe(): SpeechSynthesisVoice[] {
  if (typeof window === "undefined" || !window.speechSynthesis) return [];
  return window.speechSynthesis.getVoices();
}

/** Wait until the browser has loaded the voice list (Chrome loads async). */
export function waitForVoices(timeoutMs = 2500): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    const existing = getVoicesSafe();
    if (existing.length) {
      resolve(existing);
      return;
    }
    const done = () => {
      window.speechSynthesis.removeEventListener("voiceschanged", done);
      resolve(getVoicesSafe());
    };
    window.speechSynthesis.addEventListener("voiceschanged", done);
    window.setTimeout(done, timeoutMs);
  });
}

export function pickVoice(
  language: string,
  voices: SpeechSynthesisVoice[],
): { voice: SpeechSynthesisVoice | null; lang: string; warning?: string } {
  const key = language in LANG_CANDIDATES ? language : "en";
  const wanted = LANG_CANDIDATES[key];
  const ranked = [...voices]
    .map((v) => ({ v, score: scoreVoice(v, wanted) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score);

  const best = ranked[0]?.v ?? null;
  const lang = best?.lang || wanted[0];

  let warning: string | undefined;
  if (key === "mr") {
    const hasMr = voices.some((v) => normalize(v.lang).startsWith("mr"));
    if (!hasMr && best && normalize(best.lang).startsWith("hi")) {
      warning = "Marathi voice not found on this device — using Hindi voice (works well for मराठी text).";
    } else if (!hasMr && (!best || normalize(best.lang).startsWith("en"))) {
      warning =
        "No Marathi/Hindi voice installed. Install a Hindi voice in system settings, or Marathi will sound wrong.";
    }
  }

  return { voice: best, lang, warning };
}

export function buildUtterance(
  text: string,
  opts: {
    language: string;
    speed: SpeechSpeed;
    volume: number;
    voices: SpeechSynthesisVoice[];
  },
): { utterance: SpeechSynthesisUtterance; warning?: string } {
  const { voice, lang, warning } = pickVoice(opts.language, opts.voices);
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = SPEED_RATE[opts.speed];
  utterance.pitch = 1;
  utterance.volume = opts.volume;
  if (voice) utterance.voice = voice;
  return { utterance, warning };
}
