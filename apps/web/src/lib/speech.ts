/** Browser speech helpers — Indic voices, speakable text, and highlight alignment. */

export const SPEED_RATE = {
  very_slow: 0.8,
  slow: 0.95,
  normal: 1.1,
  fast: 1.25,
} as const;

export type SpeechSpeed = keyof typeof SPEED_RATE;

const PAUSE_SCALE: Record<SpeechSpeed, number> = {
  very_slow: 1.15,
  slow: 0.9,
  normal: 0.6,
  fast: 0.38,
};

const LANG_CANDIDATES: Record<string, string[]> = {
  en: ["en-IN", "en-GB", "en-US", "en"],
  hi: ["hi-IN", "hi"],
  mr: ["mr-IN", "mr", "hi-IN", "hi"],
};

const NATURAL_NAME =
  /neural|natural|online|premium|enhanced|wavenet|studio|google|microsoft|samantha|karen|moira|tessa|rishi|lekha|veena|aria|jenny|guy|sonia|davis|ryan|heera|aditi|kalpana|hemant|swara|neerja|हिन्दी|हिंदी|मराठी|hindi|marathi/;

const INDIC_VOICE_NAME = /hindi|हिन्दी|हिंदी|marathi|मराठी|lekha|heera|aditi|kalpana|hemant|swara|neerja/;

const ROBOTIC_NAME =
  /fred|albert|bad news|bahh|bells|boing|bubbles|cellos|deranged|good news|hysterical|pipe organ|trinoids|whisper|zarvox|superstar|junior|kathy|princess|ralph|alex|compact|eloquence|espeak|festival|robot/;

function normalize(lang: string) {
  return lang.toLowerCase().replace("_", "-");
}

export function isIndicLanguage(language: string) {
  return language === "hi" || language === "mr";
}

export function htmlLang(language: string) {
  if (language === "hi") return "hi-IN";
  if (language === "mr") return "mr-IN";
  return "en-IN";
}

export function speechRate(speed: SpeechSpeed) {
  return SPEED_RATE[speed] ?? SPEED_RATE.normal;
}

export function pauseScale(speed: SpeechSpeed) {
  return PAUSE_SCALE[speed] ?? PAUSE_SCALE.normal;
}

export type ClauseKind = "comma" | "stop" | "question" | "exclaim" | "continue";

export type SpeechExpression = {
  pitch: number;
  rateMul: number;
  pauseAfterMs: number;
};

export function trailingPunctKind(word: string): ClauseKind {
  const t = word.normalize("NFC").trim();
  if (!t) return "continue";
  if (/[?؟]["'”’)]*$/.test(t)) return "question";
  if (/[!！]["'”’)]*$/.test(t)) return "exclaim";
  if (/[।.]["'”’)]*$/.test(t)) return "stop";
  if (/[,;:，、]["'”’)]*$/.test(t)) return "comma";
  return "continue";
}

export function expressionForKind(
  kind: ClauseKind,
  language: string,
  clauseIndex = 0,
  speed: SpeechSpeed = "normal",
): SpeechExpression {
  const indic = isIndicLanguage(language);
  const lift = 1 + Math.sin(clauseIndex * 0.9) * 0.02;
  const scale = pauseScale(speed);
  switch (kind) {
    case "comma":
      return {
        pitch: 1.06 * lift,
        rateMul: 0.98,
        pauseAfterMs: Math.round((indic ? 240 : 200) * scale),
      };
    case "stop":
      return {
        pitch: 0.95 * lift,
        rateMul: 0.96,
        pauseAfterMs: Math.round((indic ? 420 : 340) * scale),
      };
    case "question":
      return {
        pitch: 1.18,
        rateMul: 0.94,
        pauseAfterMs: Math.round((indic ? 380 : 320) * scale),
      };
    case "exclaim":
      return {
        pitch: 1.12,
        rateMul: 1.04,
        pauseAfterMs: Math.round((indic ? 360 : 300) * scale),
      };
    default:
      return {
        pitch: 1.02 * lift,
        rateMul: 1,
        pauseAfterMs: Math.round((indic ? 90 : 70) * scale),
      };
  }
}

export function interWordPauseMs(
  speed: SpeechSpeed,
  style: "natural" | "word",
  language: string,
) {
  const scale = pauseScale(speed);
  const base =
    style === "natural"
      ? isIndicLanguage(language)
        ? 35
        : 25
      : isIndicLanguage(language)
        ? 80
        : 60;
  return Math.max(12, Math.round(base * scale));
}

export function splitWordClauses<T extends { text: string }>(
  words: T[],
): { words: T[]; kind: ClauseKind }[] {
  const clauses: { words: T[]; kind: ClauseKind }[] = [];
  let current: T[] = [];
  for (const word of words) {
    current.push(word);
    const kind = trailingPunctKind(word.text);
    if (kind !== "continue") {
      clauses.push({ words: current, kind });
      current = [];
    }
  }
  if (current.length) clauses.push({ words: current, kind: "continue" });
  return clauses;
}

function inferredLang(voice: SpeechSynthesisVoice) {
  const name = voice.name.toLowerCase();
  if (/marathi|मराठी/.test(name)) return "mr-in";
  if (/hindi|हिन्दी|हिंदी|lekha/.test(name)) return "hi-in";
  return normalize(voice.lang || "");
}

export function scoreVoice(voice: SpeechSynthesisVoice, wanted: string[]): number {
  const vLang = inferredLang(voice);
  const vName = voice.name.toLowerCase();
  let score = 0;

  wanted.forEach((code, i) => {
    const c = normalize(code);
    if (vLang === c) score += 100 - i * 10;
    else if (vLang.startsWith(c.split("-")[0])) score += 40 - i * 5;
  });

  if (NATURAL_NAME.test(vName)) score += 40;
  if (INDIC_VOICE_NAME.test(vName)) score += 55;
  if (!voice.localService) score += 30;
  else score -= 8;

  if (ROBOTIC_NAME.test(vName)) score -= 90;

  const primary = wanted[0]?.split("-")[0];
  if (primary && primary !== "en" && vLang.startsWith("en")) score -= 80;
  if ((primary === "hi" || primary === "mr") && vLang.startsWith("en")) score -= 40;

  return score;
}

export function getVoicesSafe(): SpeechSynthesisVoice[] {
  if (typeof window === "undefined" || !window.speechSynthesis) return [];
  return window.speechSynthesis.getVoices();
}

/** Wait until Chrome attaches cloud voices (Google हिन्दी often arrives after locals). */
export function waitForVoices(timeoutMs = 2800): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      resolve([]);
      return;
    }

    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      window.speechSynthesis.removeEventListener("voiceschanged", onChange);
      window.clearTimeout(timer);
      resolve(getVoicesSafe());
    };

    const onChange = () => {
      if (getVoicesSafe().some((v) => !v.localService)) finish();
    };

    window.speechSynthesis.addEventListener("voiceschanged", onChange);
    const timer = window.setTimeout(finish, timeoutMs);

    const first = getVoicesSafe();
    if (first.some((v) => !v.localService)) {
      finish();
      return;
    }
    if (first.length) {
      window.setTimeout(() => {
        if (!settled) finish();
      }, 450);
    }
  });
}

export function voicesForLanguage(
  language: string,
  voices: SpeechSynthesisVoice[],
): SpeechSynthesisVoice[] {
  const key = language in LANG_CANDIDATES ? language : "en";
  const wanted = LANG_CANDIDATES[key];
  return [...voices]
    .map((v) => ({ v, score: scoreVoice(v, wanted) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.v);
}

export function pickVoice(
  language: string,
  voices: SpeechSynthesisVoice[],
  preferredVoiceURI?: string | null,
): { voice: SpeechSynthesisVoice | null; lang: string; warning?: string } {
  const key = language in LANG_CANDIDATES ? language : "en";
  const wanted = LANG_CANDIDATES[key];
  const ranked = voicesForLanguage(language, voices);

  const preferred = preferredVoiceURI
    ? ranked.find((v) => v.voiceURI === preferredVoiceURI)
    : null;

  const best = preferred ?? ranked[0] ?? null;
  // lang must match the chosen voice or Chrome silently falls back to English.
  const lang = best?.lang || wanted[0];

  let warning: string | undefined;
  if (key === "mr") {
    const hasMr = voices.some((v) => inferredLang(v).startsWith("mr"));
    if (!hasMr && best && inferredLang(best).startsWith("hi")) {
      warning = "Marathi voice not found on this device — using Hindi, which reads मराठी clearly.";
    } else if (!hasMr && (!best || inferredLang(best).startsWith("en"))) {
      warning =
        "No Marathi/Hindi voice installed. In Chrome, open chrome://settings/languages and add Hindi.";
    }
  } else if (key === "hi" && (!best || inferredLang(best).startsWith("en"))) {
    warning =
      "No Hindi voice found. Chrome or Edge with a Google हिन्दी voice will pronounce this correctly.";
  } else if (best && ROBOTIC_NAME.test(best.name.toLowerCase()) && ranked.length <= 1) {
    warning =
      "This device only has a basic system voice. Chrome or Edge usually has a more natural Google/Microsoft voice.";
  }

  return { voice: best, lang, warning };
}

export function prepareSpeakableText(text: string) {
  return text
    .normalize("NFC")
    .replace(/[\u200B\uFEFF]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Strip trailing punctuation so isolated-word TTS does not say "purna viram". */
export function speakableWord(text: string) {
  const nfc = prepareSpeakableText(text);
  return nfc.replace(/[.,!?;:'"“”‘’()[\]{}।]+$/g, "").trim() || nfc;
}

export function speechWeight(text: string) {
  const clean = speakableWord(text).replace(/\s+/g, "");
  if (!clean) return 0.4;
  try {
    const seg = new Intl.Segmenter("hi", { granularity: "grapheme" });
    return Math.max(1, [...seg.segment(clean)].length);
  } catch {
    return Math.max(1, clean.length);
  }
}

export function defaultMsPerGrapheme(language: string) {
  return isIndicLanguage(language) ? 170 : 58;
}

export function minWordDurationMs(text: string, language: string, speed: SpeechSpeed) {
  const weight = speechWeight(text);
  const ms = (weight * defaultMsPerGrapheme(language)) / speechRate(speed);
  const floor = isIndicLanguage(language) ? 160 : 120;
  return Math.max(floor, Math.min(1400, ms));
}

export type CharRange = { start: number; end: number };

export function wordIndexAtChar(ranges: CharRange[], charIndex: number): number {
  if (!ranges.length) return 0;
  if (charIndex < 0) return 0;
  for (let i = 0; i < ranges.length; i++) {
    const r = ranges[i];
    if (charIndex >= r.start && charIndex < r.end) return i;
  }
  for (let i = 0; i < ranges.length; i++) {
    if (charIndex < ranges[i].start) return i;
  }
  return ranges.length - 1;
}

export function wordIndexAtElapsed(
  weights: number[],
  elapsedMs: number,
  msPerUnit: number,
  rate: number,
): number {
  if (!weights.length) return 0;
  const unit = Math.max(40, msPerUnit);
  const target = (elapsedMs * rate) / unit;
  let acc = 0;
  for (let i = 0; i < weights.length; i++) {
    acc += Math.max(0.4, weights[i]);
    if (target < acc) return i;
  }
  return weights.length - 1;
}

/** Chrome garbage-collects utterances unless we keep a live reference. */
const speechHold: { utterance: SpeechSynthesisUtterance | null } = { utterance: null };
let keepAliveTimer: number | null = null;

function startSpeechKeepAlive() {
  stopSpeechKeepAlive();
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  keepAliveTimer = window.setInterval(() => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.resume();
    }
  }, 8000);
}

export function stopSpeechKeepAlive() {
  if (keepAliveTimer != null) {
    window.clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

export function cancelSpeech() {
  stopSpeechKeepAlive();
  speechHold.utterance = null;
  if (typeof window !== "undefined") {
    window.speechSynthesis?.cancel();
  }
}

export function buildUtterance(
  text: string,
  opts: {
    language: string;
    speed: SpeechSpeed;
    volume: number;
    voices: SpeechSynthesisVoice[];
    preferredVoiceURI?: string | null;
    pitch?: number;
    rateMul?: number;
    keepAlive?: boolean;
  },
): { utterance: SpeechSynthesisUtterance; warning?: string } {
  const { voice, lang, warning } = pickVoice(opts.language, opts.voices, opts.preferredVoiceURI);
  const utterance = new SpeechSynthesisUtterance(prepareSpeakableText(text));
  const rate = speechRate(opts.speed) * (opts.rateMul ?? 1);
  utterance.rate = Math.min(1.4, Math.max(0.55, rate));
  utterance.pitch = Math.min(1.3, Math.max(0.85, opts.pitch ?? 1));
  utterance.volume = opts.volume;
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang || lang;
  } else {
    utterance.lang = lang;
  }
  speechHold.utterance = utterance;
  if (opts.keepAlive === false) stopSpeechKeepAlive();
  else startSpeechKeepAlive();
  return { utterance, warning };
}

if (typeof window !== "undefined" && window.speechSynthesis) {
  window.speechSynthesis.getVoices();
}
