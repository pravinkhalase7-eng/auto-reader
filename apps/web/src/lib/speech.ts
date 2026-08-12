/** Browser speech helpers — prefer neural/cloud voices so reading sounds human. */

export const SPEED_RATE = {
  // Too-slow rates make even good voices sound robotic.
  very_slow: 0.82,
  slow: 0.94,
  normal: 1.0,
} as const;

export type SpeechSpeed = keyof typeof SPEED_RATE;

const LANG_CANDIDATES: Record<string, string[]> = {
  en: ["en-IN", "en-GB", "en-US", "en"],
  hi: ["hi-IN", "hi"],
  // Most desktops lack mr-IN; Hindi voices read Devanagari far better than English.
  mr: ["mr-IN", "mr", "hi-IN", "hi"],
};

const NATURAL_NAME =
  /neural|natural|online|premium|enhanced|wavenet|studio|google|microsoft|samantha|karen|moira|tessa|rishi|lekha|veena|aria|jenny|guy|sonia|davis|ryan|heera|aditi/;

const ROBOTIC_NAME =
  /fred|albert|bad news|bahh|bells|boing|bubbles|cellos|deranged|good news|hysterical|pipe organ|trinoids|whisper|zarvox|superstar|junior|kathy|princess|ralph|alex|compact|eloquence|espeak|festival|robot/;

function normalize(lang: string) {
  return lang.toLowerCase().replace("_", "-");
}

export function scoreVoice(voice: SpeechSynthesisVoice, wanted: string[]): number {
  const vLang = normalize(voice.lang);
  const vName = voice.name.toLowerCase();
  let score = 0;

  wanted.forEach((code, i) => {
    const c = normalize(code);
    if (vLang === c) score += 100 - i * 10;
    else if (vLang.startsWith(c.split("-")[0])) score += 40 - i * 5;
  });

  if (NATURAL_NAME.test(vName)) score += 40;
  // Chrome/Edge cloud voices (localService=false) are far more human than compact OS voices.
  if (!voice.localService) score += 25;
  else score -= 8;

  if (ROBOTIC_NAME.test(vName)) score -= 90;

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
    ? ranked.find((v) => v.voiceURI === preferredVoiceURI) ||
      voices.find((v) => v.voiceURI === preferredVoiceURI)
    : null;

  const best = preferred ?? ranked[0] ?? null;
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
  } else if (best && ROBOTIC_NAME.test(best.name.toLowerCase()) && ranked.length <= 1) {
    warning =
      "This device only has a basic system voice. Chrome or Edge usually has a more natural Google/Microsoft voice.";
  }

  return { voice: best, lang, warning };
}

/** Chrome garbage-collects utterances unless we keep a live reference. */
let activeUtterance: SpeechSynthesisUtterance | null = null;
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
  activeUtterance = null;
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
  },
): { utterance: SpeechSynthesisUtterance; warning?: string } {
  const { voice, lang, warning } = pickVoice(opts.language, opts.voices, opts.preferredVoiceURI);
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = SPEED_RATE[opts.speed];
  utterance.pitch = 1;
  utterance.volume = opts.volume;
  if (voice) utterance.voice = voice;
  activeUtterance = utterance;
  startSpeechKeepAlive();
  return { utterance, warning };
}
