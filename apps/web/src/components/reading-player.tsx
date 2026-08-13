"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pause,
  Play,
  RotateCcw,
  SkipBack,
  SkipForward,
  Volume2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useReaderStore } from "@/store/reader-store";
import type { AudioAsset, LessonContent, SpeedOption } from "@/types";
import { cn } from "@/lib/utils";
import {
  buildUtterance,
  cancelSpeech,
  expressionForKind,
  interWordPauseMs,
  speakableWord,
  trailingPunctKind,
  voicesForLanguage,
  waitForVoices,
  hasNativeVoice,
  voiceOptionLabel,
  type SpeechExpression,
} from "@/lib/speech";
import { ApiError } from "@/lib/api";
import {
  elevenLabsVoiceId,
  elevenLabsVoiceURI,
  fetchElevenLabsVoices,
  isElevenLabsVoice,
  playElevenLabsSpeech,
  primeElevenLabsPlayback,
  type ElevenLabsVoice,
} from "@/lib/elevenlabs";
import { cancelWordPreview } from "@/lib/preview-word";

type FlatWord = {
  id: string;
  text: string;
  sentenceId: string;
  paragraphId: string;
};

type FlatSentence = {
  id: string;
  paragraphId: string;
  words: FlatWord[];
  text: string;
  globalStart: number;
};

type FlatParagraph = {
  id: string;
  startWord: number;
  startSentence: number;
};

function flattenContent(content: LessonContent) {
  const words: FlatWord[] = [];
  const sentences: FlatSentence[] = [];
  const paragraphs: FlatParagraph[] = [];

  for (const section of content.sections) {
    for (const para of section.paragraphs) {
      const startWord = words.length;
      const startSentence = sentences.length;

      for (const sent of para.sentences) {
        const sentWords: FlatWord[] = [];
        const globalStart = words.length;

        sent.words.forEach((w) => {
          const token = w.text.normalize("NFC");
          const flat = {
            id: w.id,
            text: token,
            sentenceId: sent.id,
            paragraphId: para.id,
          };
          sentWords.push(flat);
          words.push(flat);
        });

        if (sentWords.length) {
          sentences.push({
            id: sent.id,
            paragraphId: para.id,
            words: sentWords,
            text: sentWords.map((w) => w.text).join(" "),
            globalStart,
          });
        }
      }

      paragraphs.push({
        id: para.id,
        startWord,
        startSentence,
      });
    }
  }

  return { words, sentences, paragraphs };
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

export function ReadingPlayer({
  content,
}: {
  content: LessonContent;
  audio: AudioAsset | null;
}) {
  const {
    mode,
    speed,
    playbackStyle,
    volume,
    preferredVoiceURI,
    isPlaying,
    paragraphIndex,
    activeWordId,
    setPlaying,
    setActive,
    setSpeed,
    setPlaybackStyle,
    setVolume,
    setPreferredVoiceURI,
    setParagraphIndex,
    setMode,
    reset,
  } = useReaderStore();

  const { words, sentences, paragraphs } = useMemo(
    () => flattenContent(content),
    [content],
  );

  const [voiceWarning, setVoiceWarning] = useState<string | null>(null);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [elevenVoices, setElevenVoices] = useState<ElevenLabsVoice[]>([]);
  const [elevenEnabled, setElevenEnabled] = useState(false);

  const cancelledRef = useRef(false);
  const pausedRef = useRef(false);
  const runIdRef = useRef(0);
  const wordCursorRef = useRef(0);
  const sentenceCursorRef = useRef(0);
  const skipElevenRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    skipElevenRef.current = false;
    setVoiceWarning(null);
    setPreferredVoiceURI(null);
    waitForVoices().then((voices) => {
      if (cancelled) return;
      setAvailableVoices(voicesForLanguage(content.language, voices));
    });
    fetchElevenLabsVoices().then((result) => {
      if (cancelled) return;
      setElevenEnabled(result.enabled);
      setElevenVoices(result.voices);
      if (!result.enabled) {
        setVoiceWarning("ElevenLabs voices did not load. Refresh the page.");
        return;
      }
      if (content.language !== "mr" || !result.voices.length) return;
      waitForVoices().then((voices) => {
        if (cancelled) return;
        if (hasNativeVoice("mr", voices)) return;
        skipElevenRef.current = false;
        setPreferredVoiceURI(elevenLabsVoiceURI(result.voices[0].id));
        setVoiceWarning(
          "This device has no Marathi voice. ElevenLabs is selected so मराठी is pronounced clearly. Hover a word, or click it, to hear it.",
        );
      });
    });
    return () => {
      cancelled = true;
    };
  }, [content.language, setPreferredVoiceURI]);

  useEffect(() => {
    if (!isElevenLabsVoice(preferredVoiceURI) || !elevenVoices.length) return;
    const selected = elevenLabsVoiceId(preferredVoiceURI);
    if (selected && elevenVoices.some((voice) => voice.id === selected)) return;
    setPreferredVoiceURI(elevenLabsVoiceURI(elevenVoices[0].id));
  }, [elevenVoices, preferredVoiceURI, setPreferredVoiceURI]);

  const activateGlobal = useCallback(
    (index: number) => {
      const w = words[index];
      if (!w) return;
      wordCursorRef.current = index;
      setActive(w.id, w.sentenceId, w.paragraphId);
      const pIdx = paragraphs.findIndex((p) => p.id === w.paragraphId);
      if (pIdx >= 0) setParagraphIndex(pIdx);
    },
    [paragraphs, setActive, setParagraphIndex, words],
  );

  const speakUtterance = useCallback(
    async (
      text: string,
      voices: SpeechSynthesisVoice[],
      handlers?: {
        onStart?: () => void;
        expression?: SpeechExpression;
        keepAlive?: boolean;
        onProgress?: (elapsedMs: number, durationMs: number) => void;
      },
    ) => {
      const elevenId = elevenLabsVoiceId(preferredVoiceURI);
      if (elevenId && !skipElevenRef.current) {
        try {
          return await playElevenLabsSpeech({
            text,
            voiceId: elevenId,
            speed,
            language: content.language,
            volume,
            onStart: handlers?.onStart,
            onProgress: handlers?.onProgress,
            isCancelled: () => cancelledRef.current,
          });
        } catch (err) {
          skipElevenRef.current = true;
          const message =
            err instanceof ApiError || err instanceof Error
              ? err.message
              : "I couldn't use the ElevenLabs voice this time.";
          setVoiceWarning(`${message} Using this device instead.`);
        }
      }
      if (typeof window === "undefined" || !window.speechSynthesis) return "error";
      const browserVoices = voices.length ? voices : await waitForVoices();
      return new Promise<"ended" | "error" | "interrupted">((resolve) => {
        const { utterance, warning } = buildUtterance(text, {
          language: content.language,
          speed,
          volume,
          voices: browserVoices,
          preferredVoiceURI: skipElevenRef.current ? null : preferredVoiceURI,
          pitch: handlers?.expression?.pitch,
          rateMul: handlers?.expression?.rateMul,
          keepAlive: handlers?.keepAlive ?? false,
        });
        if (warning) setVoiceWarning(warning);
        utterance.onstart = () => handlers?.onStart?.();
        utterance.onend = () => resolve("ended");
        utterance.onerror = (event) => {
          const err = event.error;
          resolve(err === "interrupted" || err === "canceled" ? "interrupted" : "error");
        };
        window.speechSynthesis.speak(utterance);
      });
    },
    [content.language, preferredVoiceURI, speed, volume],
  );

  const waitIfActive = useCallback(async (ms: number, runId: number) => {
    let left = ms;
    while (left > 0) {
      if (cancelledRef.current || runIdRef.current !== runId) return false;
      while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
        await sleep(80);
      }
      if (cancelledRef.current || runIdRef.current !== runId) return false;
      const slice = Math.min(40, left);
      await sleep(slice);
      left -= slice;
    }
    return true;
  }, []);

  const narrationChunks = useCallback(
    (startPara: number) => {
      const chunks: { paragraphId: string; paragraphIndex: number; text: string }[] = [];
      for (let p = startPara; p < paragraphs.length; p++) {
        const para = paragraphs[p];
        const paraSentences = sentences.filter((s) => s.paragraphId === para.id);
        const texts = paraSentences.map((s) => s.text).filter(Boolean);
        if (!texts.length) continue;
        const joined = texts.join(" ");
        if (joined.length <= 360) {
          chunks.push({ paragraphId: para.id, paragraphIndex: p, text: joined });
        } else {
          for (const text of texts) {
            chunks.push({ paragraphId: para.id, paragraphIndex: p, text });
          }
        }
      }
      return chunks;
    },
    [paragraphs, sentences],
  );

  const finishPlayback = useCallback(
    (runId: number) => {
      if (runIdRef.current !== runId) return;
      pausedRef.current = false;
      wordCursorRef.current = 0;
      sentenceCursorRef.current = 0;
      setPlaying(false);
      setActive(null);
      setParagraphIndex(0);
      document
        .querySelector<HTMLElement>("[data-lesson-scroll]")
        ?.scrollTo({ top: 0, behavior: "smooth" });
    },
    [setActive, setParagraphIndex, setPlaying],
  );

  /** Fluent teacher narration — whole phrases, no word highlight. */
  const speakDirect = useCallback(
    async (startPara: number) => {
      if (typeof window === "undefined") return;
      if (mode === "read") {
        setPlaying(true);
        return;
      }

      const runId = ++runIdRef.current;
      cancelledRef.current = false;
      pausedRef.current = false;
      setPlaying(true);
      setActive(null, null, paragraphs[startPara]?.id ?? null);
      cancelSpeech();
      await sleep(60);

      const voices = isElevenLabsVoice(preferredVoiceURI) ? [] : await waitForVoices();
      const chunks = narrationChunks(Math.max(0, startPara));

      for (const chunk of chunks) {
        if (cancelledRef.current || runIdRef.current !== runId) return;
        while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
          await sleep(80);
        }
        if (cancelledRef.current || runIdRef.current !== runId) return;

        setParagraphIndex(chunk.paragraphIndex);
        setActive(null, null, chunk.paragraphId);
        sentenceCursorRef.current = paragraphs[chunk.paragraphIndex]?.startSentence ?? 0;
        wordCursorRef.current = paragraphs[chunk.paragraphIndex]?.startWord ?? 0;

        const result = await speakUtterance(chunk.text, voices, {
          keepAlive: true,
          expression: { pitch: 1.04, rateMul: 1, pauseAfterMs: 0 },
          onStart: () => setActive(null, null, chunk.paragraphId),
        });
        if (cancelledRef.current || runIdRef.current !== runId) return;
        if (result === "interrupted") return;
        await waitIfActive(220, runId);
      }

      if (runIdRef.current === runId) {
        finishPlayback(runId);
      }
    },
    [
      finishPlayback,
      mode,
      narrationChunks,
      paragraphs,
      preferredVoiceURI,
      setActive,
      setParagraphIndex,
      setPlaying,
      speakUtterance,
      waitIfActive,
    ],
  );

  /** One spoken word = one highlighted word. Advance only after that utterance ends. */
  const speakFromWord = useCallback(
    async (startWord: number) => {
      if (typeof window === "undefined") return;
      if (mode === "read") {
        setPlaying(true);
        return;
      }
      if (playbackStyle === "direct") {
        let para = 0;
        for (let i = 0; i < paragraphs.length; i++) {
          if (startWord >= paragraphs[i].startWord) para = i;
        }
        await speakDirect(para);
        return;
      }

      const runId = ++runIdRef.current;
      cancelledRef.current = false;
      pausedRef.current = false;
      setPlaying(true);
      cancelSpeech();
      await sleep(60);

      const from = Math.max(0, Math.min(startWord, Math.max(0, words.length - 1)));

      if (isElevenLabsVoice(preferredVoiceURI)) {
        for (let s = 0; s < sentences.length; s++) {
          const sentence = sentences[s];
          if (sentence.globalStart + sentence.words.length - 1 < from) continue;
          if (cancelledRef.current || runIdRef.current !== runId) return;
          while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
            await sleep(80);
          }
          if (cancelledRef.current || runIdRef.current !== runId) return;
          sentenceCursorRef.current = s;
          const pIdx = paragraphs.findIndex((p) => p.id === sentence.paragraphId);
          if (pIdx >= 0) setParagraphIndex(pIdx);
          const startLocal = Math.max(0, from - sentence.globalStart);
          const slice = sentence.words.slice(startLocal);
          const spoken = slice.map((word) => word.text).join(" ").trim();
          if (!spoken) continue;
          const result = await speakUtterance(spoken, [], {
            keepAlive: true,
            onStart: () => activateGlobal(sentence.globalStart + startLocal),
            onProgress: (elapsedMs, durationMs) => {
              if (!durationMs) return;
              const i = Math.min(
                slice.length - 1,
                Math.max(0, Math.floor((elapsedMs / durationMs) * slice.length)),
              );
              activateGlobal(sentence.globalStart + startLocal + i);
            },
          });
          if (cancelledRef.current || runIdRef.current !== runId) return;
          if (result === "interrupted") return;
          if (result === "error") {
            setVoiceWarning("ElevenLabs could not play that line. Try Play again, or use This device.");
            return;
          }
        }
        if (runIdRef.current === runId) finishPlayback(runId);
        return;
      }

      if (!window.speechSynthesis) return;
      const voices = await waitForVoices();
      const natural = playbackStyle === "natural";

      for (let s = 0; s < sentences.length; s++) {
        const sentence = sentences[s];
        if (sentence.globalStart + sentence.words.length - 1 < from) continue;

        sentenceCursorRef.current = s;
        const pIdx = paragraphs.findIndex((p) => p.id === sentence.paragraphId);
        if (pIdx >= 0) setParagraphIndex(pIdx);

        for (let i = 0; i < sentence.words.length; i++) {
          const global = sentence.globalStart + i;
          if (global < from) continue;
          if (cancelledRef.current || runIdRef.current !== runId) return;
          while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
            await sleep(80);
          }
          if (cancelledRef.current || runIdRef.current !== runId) return;

          const token = sentence.words[i].text;
          const spoken = speakableWord(token);
          if (!spoken) {
            activateGlobal(global);
            continue;
          }

          const kind = trailingPunctKind(token);
          const expression = expressionForKind(kind, content.language, global, speed);
          let started = false;
          const t0 = performance.now();
          const result = await speakUtterance(spoken, voices, {
            expression,
            onStart: () => {
              started = true;
              activateGlobal(global);
            },
          });

          if (!started) activateGlobal(global);
          if (cancelledRef.current || runIdRef.current !== runId) return;
          if (result === "interrupted") return;

          const elapsed = performance.now() - t0;
          if (result === "ended" && elapsed < 80) {
            await waitIfActive(80 - elapsed, runId);
          }
          if (cancelledRef.current || runIdRef.current !== runId) return;

          const pause =
            kind === "continue"
              ? interWordPauseMs(speed, natural ? "natural" : "word", content.language)
              : expression.pauseAfterMs;
          await waitIfActive(pause, runId);
        }
      }

      if (runIdRef.current === runId) finishPlayback(runId);
    },
    [
      activateGlobal,
      content.language,
      finishPlayback,
      mode,
      paragraphs,
      playbackStyle,
      preferredVoiceURI,
      sentences,
      setParagraphIndex,
      setPlaying,
      speakDirect,
      speakUtterance,
      speed,
      waitIfActive,
      words.length,
    ],
  );

  const firstWordForParagraph = useCallback(
    (pIndex: number) => paragraphs[Math.max(0, Math.min(pIndex, paragraphs.length - 1))]?.startWord ?? 0,
    [paragraphs],
  );

  const stopAll = useCallback(() => {
    cancelledRef.current = true;
    pausedRef.current = false;
    runIdRef.current += 1;
    cancelWordPreview();
    setPlaying(false);
  }, [setPlaying]);

  const play = () => {
    cancelWordPreview();
    primeElevenLabsPlayback();
    void speakFromWord(firstWordForParagraph(paragraphIndex));
  };

  const pause = () => {
    pausedRef.current = true;
    cancelSpeech();
    setPlaying(false);
  };

  const resume = () => {
    pausedRef.current = false;
    primeElevenLabsPlayback();
    void speakFromWord(wordCursorRef.current);
  };

  const restart = () => {
    stopAll();
    reset();
    sentenceCursorRef.current = 0;
    wordCursorRef.current = 0;
    primeElevenLabsPlayback();
    window.setTimeout(() => void speakFromWord(0), 60);
  };

  useEffect(() => () => stopAll(), [stopAll]);

  const activeIndex = words.findIndex((w) => w.id === activeWordId);
  const atStart = !isPlaying && paragraphIndex === 0 && !activeWordId;
  const progress = atStart
    ? 0
    : playbackStyle === "direct"
      ? paragraphs.length === 0
        ? 0
        : ((paragraphIndex + 1) / paragraphs.length) * 100
      : words.length === 0
        ? 0
        : activeIndex < 0
          ? 0
          : ((activeIndex + 1) / words.length) * 100;

  return (
    <div className="rounded-3xl border border-teal-900/10 bg-white/95 p-4 shadow-lg">
      <div className="mb-3 flex flex-wrap gap-2">
        {(
          [
            ["listen_read", "Listen + Read"],
            ["listen", "Listen"],
            ["read", "Read"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setMode(value)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold",
              mode === value ? "bg-teal-700 text-white" : "bg-teal-50 text-teal-900",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            stopAll();
            setPlaybackStyle("direct");
          }}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            playbackStyle === "direct" ? "bg-amber-500 text-white" : "bg-amber-50 text-amber-950",
          )}
        >
          Direct reading
        </button>
        <button
          type="button"
          onClick={() => {
            stopAll();
            setPlaybackStyle("natural");
          }}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            playbackStyle === "natural" ? "bg-amber-500 text-white" : "bg-amber-50 text-amber-950",
          )}
        >
          Natural reading
        </button>
        <button
          type="button"
          onClick={() => {
            stopAll();
            setPlaybackStyle("word");
          }}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            playbackStyle === "word" ? "bg-amber-500 text-white" : "bg-amber-50 text-amber-950",
          )}
        >
          Word by word
        </button>
      </div>

      <p className="mb-1 text-xs font-semibold text-teal-800/80">Voice</p>
      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            stopAll();
            setPreferredVoiceURI(availableVoices[0]?.voiceURI ?? null);
          }}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            !isElevenLabsVoice(preferredVoiceURI) ? "bg-teal-700 text-white" : "bg-teal-50 text-teal-900",
          )}
        >
          This device
        </button>
        <button
          type="button"
          onClick={() => {
            stopAll();
            skipElevenRef.current = false;
            setVoiceWarning(null);
            const first = elevenVoices[0]?.id || "default";
            setPreferredVoiceURI(elevenLabsVoiceURI(first));
          }}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            isElevenLabsVoice(preferredVoiceURI) ? "bg-teal-700 text-white" : "bg-teal-50 text-teal-900",
          )}
        >
          ElevenLabs
        </button>
      </div>
      {isElevenLabsVoice(preferredVoiceURI) && elevenVoices.length > 1 ? (
        <label className="mb-3 flex flex-col gap-1 text-sm text-teal-900">
          ElevenLabs voice
          <select
            className="rounded-xl border border-teal-900/15 bg-white px-2 py-1.5"
            value={preferredVoiceURI ?? ""}
            onChange={(e) => {
              stopAll();
              skipElevenRef.current = false;
              setVoiceWarning(null);
              setPreferredVoiceURI(e.target.value || null);
            }}
            aria-label="ElevenLabs voice"
          >
            {elevenVoices.map((voice) => (
              <option key={voice.id} value={elevenLabsVoiceURI(voice.id)}>
                {voice.name}
                {voice.accent ? ` · ${voice.accent}` : ""}
              </option>
            ))}
          </select>
          <span className="text-xs font-normal text-teal-800/70">
            {content.language === "mr"
              ? "ElevenLabs v3 reads मराठी. Classroom voices work with a free key."
              : "Classroom voices that work with a free ElevenLabs key. Voice Library voices need a paid plan."}
          </span>
        </label>
      ) : null}
      {!isElevenLabsVoice(preferredVoiceURI) && availableVoices.length > 0 ? (
        <label className="mb-3 flex flex-col gap-1 text-sm text-teal-900">
          Device voice
          <select
            className="rounded-xl border border-teal-900/15 bg-white px-2 py-1.5"
            value={preferredVoiceURI ?? availableVoices[0]?.voiceURI ?? ""}
            onChange={(e) => {
              stopAll();
              setPreferredVoiceURI(e.target.value || null);
            }}
            aria-label="Device voice"
          >
            {availableVoices.map((v) => (
              <option key={v.voiceURI} value={v.voiceURI}>
                {voiceOptionLabel(v, content.language)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {!elevenEnabled ? (
        <p className="mb-3 text-xs text-amber-800">
          ElevenLabs did not load. Refresh this page after the API has the key.
        </p>
      ) : null}

      <div className="mb-3 h-2 overflow-hidden rounded-full bg-teal-900/10">
        <div
          className="h-full bg-teal-600 transition-all duration-150"
          style={{ width: `${Math.max(0, progress)}%` }}
        />
      </div>

      {voiceWarning ? (
        <p className="mb-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-950" role="status">
          {voiceWarning}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button
          variant="outline"
          size="icon"
          aria-label="Previous paragraph"
          onClick={() => {
            stopAll();
            const next = Math.max(0, paragraphIndex - 1);
            setParagraphIndex(next);
            wordCursorRef.current = firstWordForParagraph(next);
          }}
        >
          <SkipBack className="h-4 w-4" />
        </Button>
        {!isPlaying ? (
          <Button
            size="lg"
            aria-label="Play"
            disabled={words.length === 0}
            onClick={pausedRef.current ? resume : play}
          >
            <Play className="h-5 w-5" /> Play
          </Button>
        ) : (
          <Button size="lg" variant="secondary" aria-label="Pause" onClick={pause}>
            <Pause className="h-5 w-5" /> Pause
          </Button>
        )}
        <Button variant="outline" size="icon" aria-label="Restart" onClick={restart}>
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          aria-label="Next paragraph"
          onClick={() => {
            stopAll();
            const next = Math.min(paragraphs.length - 1, paragraphIndex + 1);
            setParagraphIndex(next);
            wordCursorRef.current = firstWordForParagraph(next);
          }}
        >
          <SkipForward className="h-4 w-4" />
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        <label className="flex items-center gap-2 text-teal-900">
          Speed
          <select
            className="rounded-xl border border-teal-900/15 bg-white px-2 py-1"
            value={speed}
            onChange={(e) => setSpeed(e.target.value as SpeedOption)}
            aria-label="Reading speed"
          >
            <option value="very_slow">Very Slow</option>
            <option value="slow">Slow</option>
            <option value="normal">Normal</option>
            <option value="fast">Fast</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-teal-900">
          <Volume2 className="h-4 w-4" />
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            aria-label="Volume"
          />
        </label>
      </div>
    </div>
  );
}
