export type MicState = "idle" | "requesting_permission" | "listening" | "processing" | "error";

export type SpeechResultHandler = (transcript: string, isFinal: boolean) => void;
export type SpeechErrorHandler = (message: string) => void;

export interface SpeechProvider {
  readonly name: string;
  isSupported(): boolean;
  start(onResult: SpeechResultHandler, onError: SpeechErrorHandler, onEnd: () => void): Promise<void>;
  stop(): void;
}

type RecognitionCtor = new () => SpeechRecognitionLike;

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }> }) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort?: () => void;
};

function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export class BrowserSpeechProvider implements SpeechProvider {
  readonly name = "browser";
  private recognition: SpeechRecognitionLike | null = null;

  isSupported(): boolean {
    return Boolean(getRecognitionCtor());
  }

  async start(onResult: SpeechResultHandler, onError: SpeechErrorHandler, onEnd: () => void): Promise<void> {
    const Ctor = getRecognitionCtor();
    if (!Ctor) {
      onError("Voice input isn’t available in this browser. You can still type to Pavi.");
      return;
    }
    this.stop();
    const recognition = new Ctor();
    this.recognition = recognition;
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const last = event.results[event.results.length - 1];
      if (!last) return;
      onResult(last[0].transcript, Boolean(last.isFinal));
    };
    recognition.onerror = (event) => {
      const code = event.error || "error";
      if (code === "not-allowed") onError("Microphone permission was denied.");
      else if (code === "no-speech") onError("I didn’t catch that. Please try again.");
      else onError("I couldn’t hear that clearly. Please try again.");
    };
    recognition.onend = () => onEnd();
    recognition.start();
  }

  stop(): void {
    try {
      this.recognition?.stop();
    } catch {
      /* already stopped */
    }
    this.recognition = null;
  }
}

/** Reserved for a future Google Cloud STT backend. */
export class GoogleSpeechProvider implements SpeechProvider {
  readonly name = "google";
  isSupported(): boolean {
    return false;
  }
  async start(): Promise<void> {
    throw new Error("Google speech recognition is not enabled in this MVP.");
  }
  stop(): void {}
}

export function getSpeechProvider(): SpeechProvider {
  return new BrowserSpeechProvider();
}
