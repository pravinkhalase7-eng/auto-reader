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
import type {
  AudioAsset,
  HardWordExplain,
  HindiExplainResponse,
  HindiSentenceExplain,
  LessonContent,
  SpeedOption,
} from "@/types";
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
import { ApiError, api } from "@/lib/api";
import {
  elevenLabsVoiceId,
  elevenLabsVoiceURI,
  fetchElevenLabsVoices,
  isElevenLabsVoice,
  playElevenLabsSpeech,
  prefetchElevenLabsAhead,
  prefetchElevenLabsAudio,
  primeElevenLabsPlayback,
  warmElevenLabsFirst,
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
  lessonId,
}: {
  content: LessonContent;
  audio: AudioAsset | null;
  lessonId: string;
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
  const [hasDeviceMarathi, setHasDeviceMarathi] = useState(false);
  const [elevenVoices, setElevenVoices] = useState<ElevenLabsVoice[]>([]);
  const [elevenEnabled, setElevenEnabled] = useState(false);
  const [teachLoading, setTeachLoading] = useState(false);
  const [teachNote, setTeachNote] = useState<string | null>(null);
  const [activeTeach, setActiveTeach] = useState<HindiSentenceExplain | null>(null);
  const [reviewHardWords, setReviewHardWords] = useState<HardWordExplain[] | null>(null);
  const teachCacheRef = useRef<HindiExplainResponse | null>(null);

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
    if (content.language === "mr") {
      setPreferredVoiceURI(elevenLabsVoiceURI("default"));
    } else {
      setPreferredVoiceURI(null);
    }
    waitForVoices().then((voices) => {
      if (cancelled) return;
      const nativeMr = hasNativeVoice("mr", voices);
      setHasDeviceMarathi(nativeMr);
      setAvailableVoices(voicesForLanguage(content.language, voices));
    });
    fetchElevenLabsVoices(content.language).then((result) => {
      if (cancelled) return;
      setElevenEnabled(result.enabled);
      setElevenVoices(result.voices);
      if (content.language !== "mr") return;
      waitForVoices().then((voices) => {
        if (cancelled) return;
        if (hasNativeVoice("mr", voices)) return;
        skipElevenRef.current = false;
        const voiceId = result.voices[0]?.id || "default";
        setPreferredVoiceURI(elevenLabsVoiceURI(voiceId));
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
        language?: string;
        voiceId?: string | null;
      },
    ) => {
      const speakLang = handlers?.language || content.language;
      const elevenId =
        handlers?.voiceId !== undefined
          ? handlers.voiceId
          : elevenLabsVoiceId(preferredVoiceURI);
      if (elevenId && !skipElevenRef.current) {
        try {
          return await playElevenLabsSpeech({
            text,
            voiceId: elevenId,
            speed,
            language: speakLang,
            volume,
            onStart: handlers?.onStart,
            onProgress: handlers?.onProgress,
            isCancelled: () => cancelledRef.current,
          });
        } catch (err) {
          const unauthorized =
            err instanceof ApiError &&
            (err.code === "ELEVENLABS_UNAUTHORIZED" ||
              err.code === "GOOGLE_TTS_UNAUTHORIZED" ||
              /key on this server is not accepted/i.test(err.message) ||
              /not allowed for Cloud Text-to-Speech/i.test(err.message));
          const message = unauthorized
            ? "The Google cloud voice isn't available. Check GOOGLE_AI_API_KEY / GOOGLE_CLOUD_API_KEY."
            : err instanceof ApiError || err instanceof Error
              ? err.message
              : "I couldn't use the Google cloud voice this time.";
          if (content.language === "mr" || unauthorized) {
            setVoiceWarning(message);
            return "error";
          }
          skipElevenRef.current = true;
          setVoiceWarning(`${message} Using this device instead.`);
        }
      }
      if (typeof window === "undefined" || !window.speechSynthesis) return "error";
      const browserVoices = voices.length ? voices : await waitForVoices();
      if (content.language === "mr" && !hasNativeVoice("mr", browserVoices)) {
        setVoiceWarning(
          "This device has no Marathi voice. Choose Google voice so pronunciation sounds like मराठी.",
        );
        return "error";
      }
      return new Promise<"ended" | "error" | "interrupted">((resolve) => {
        const { utterance, warning } = buildUtterance(text, {
          language: speakLang,
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
    (startPara: number, maxChars = 360) => {
      const chunks: {
        paragraphId: string;
        paragraphIndex: number;
        text: string;
        startWord: number;
        wordCount: number;
      }[] = [];
      for (let p = startPara; p < paragraphs.length; p++) {
        const para = paragraphs[p];
        const paraSentences = sentences.filter((s) => s.paragraphId === para.id);
        if (!paraSentences.length) continue;

        let buf = "";
        let bufStart = paraSentences[0].globalStart;
        let bufWords = 0;
        const flush = () => {
          const text = buf.trim();
          if (!text) return;
          chunks.push({
            paragraphId: para.id,
            paragraphIndex: p,
            text,
            startWord: bufStart,
            wordCount: bufWords,
          });
          buf = "";
          bufWords = 0;
        };

        for (const sent of paraSentences) {
          const piece = sent.text.trim();
          if (!piece) continue;
          const next = buf ? `${buf} ${piece}` : piece;
          if (buf && next.length > maxChars) {
            flush();
            buf = piece;
            bufStart = sent.globalStart;
            bufWords = sent.words.length;
          } else {
            if (!buf) bufStart = sent.globalStart;
            buf = next;
            bufWords += sent.words.length;
          }
        }
        flush();
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

  /** Fluent teacher narration — whole phrases; ElevenLabs uses large prebuffered chunks. */
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
      await sleep(40);

      const elevenId = elevenLabsVoiceId(preferredVoiceURI);
      const usingEleven = Boolean(elevenId && !skipElevenRef.current);
      const voices = usingEleven ? [] : await waitForVoices();
      // Larger chunks = far fewer ElevenLabs round-trips (main cause of buffering)
      const chunks = narrationChunks(Math.max(0, startPara), usingEleven ? 1100 : 360);

      if (usingEleven && elevenId && chunks[0]) {
        setVoiceWarning("Preparing voice…");
        try {
          await warmElevenLabsFirst({
            text: chunks[0].text,
            voiceId: elevenId,
            speed,
            language: content.language,
          });
          prefetchElevenLabsAhead(
            chunks.map((c) => ({
              text: c.text,
              voiceId: elevenId,
              speed,
              language: content.language,
            })),
            1,
            2,
          );
        } catch {
          /* speakUtterance will surface the error */
        }
        if (cancelledRef.current || runIdRef.current !== runId) return;
        setVoiceWarning(null);
      }

      for (let c = 0; c < chunks.length; c++) {
        const chunk = chunks[c];
        if (cancelledRef.current || runIdRef.current !== runId) return;
        while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
          await sleep(80);
        }
        if (cancelledRef.current || runIdRef.current !== runId) return;

        if (elevenId && usingEleven) {
          prefetchElevenLabsAhead(
            chunks.map((item) => ({
              text: item.text,
              voiceId: elevenId,
              speed,
              language: content.language,
            })),
            c + 1,
            2,
          );
        }

        setParagraphIndex(chunk.paragraphIndex);
        sentenceCursorRef.current = paragraphs[chunk.paragraphIndex]?.startSentence ?? 0;
        wordCursorRef.current = chunk.startWord;

        const highlight = playbackStyle !== "direct";
        const result = await speakUtterance(chunk.text, voices, {
          keepAlive: true,
          expression: { pitch: 1.04, rateMul: 1, pauseAfterMs: 0 },
          onStart: () => {
            if (highlight) activateGlobal(chunk.startWord);
            else setActive(null, null, chunk.paragraphId);
          },
          onProgress: highlight
            ? (elapsedMs, durationMs) => {
                if (!durationMs || chunk.wordCount < 1) return;
                const i = Math.min(
                  chunk.wordCount - 1,
                  Math.max(0, Math.floor((elapsedMs / durationMs) * chunk.wordCount)),
                );
                activateGlobal(chunk.startWord + i);
              }
            : undefined,
        });
        if (cancelledRef.current || runIdRef.current !== runId) return;
        if (result === "interrupted") return;
        if (result === "error" && usingEleven) {
            setVoiceWarning("Google voice could not play that line. Try Play again, or use This device.");
          return;
        }
        await waitIfActive(usingEleven ? 40 : 220, runId);
      }

      if (runIdRef.current === runId) {
        finishPlayback(runId);
      }
    },
    [
      activateGlobal,
      content.language,
      finishPlayback,
      mode,
      narrationChunks,
      paragraphs,
      playbackStyle,
      preferredVoiceURI,
      setActive,
      setParagraphIndex,
      setPlaying,
      speakUtterance,
      speed,
      waitIfActive,
    ],
  );

  /** Learn in Hindi: read sentence → Hindi meaning; hard words only at the end. */
  const ensureTeachGuide = useCallback(async () => {
    if (teachCacheRef.current) return teachCacheRef.current;
    setTeachLoading(true);
    setTeachNote("हिंदी में समझा रहा हूँ… Preparing Hindi help…");
    try {
      const data = await api<HindiExplainResponse>(`/lessons/${lessonId}/explain-hindi`, {
        method: "POST",
      });
      teachCacheRef.current = data;
      setTeachNote(null);
      return data;
    } catch (err) {
      const message =
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Hindi help could not load.";
      setTeachNote(message);
      throw err;
    } finally {
      setTeachLoading(false);
    }
  }, [lessonId]);

  const speakLearnHindi = useCallback(
    async (startWord: number) => {
      if (typeof window === "undefined") return;
      if (mode === "read") {
        setPlaying(true);
        return;
      }

      const runId = ++runIdRef.current;
      cancelledRef.current = false;
      pausedRef.current = false;
      setPlaying(true);
      cancelSpeech();
      primeElevenLabsPlayback();
      await sleep(40);

      let guide: HindiExplainResponse;
      try {
        guide = await ensureTeachGuide();
      } catch {
        setPlaying(false);
        return;
      }
      if (cancelledRef.current || runIdRef.current !== runId) return;

      const tipById = new Map<string, HindiSentenceExplain>();
      for (const row of guide.sentences || []) tipById.set(row.id, row);

      const from = Math.max(0, Math.min(startWord, Math.max(0, words.length - 1)));
      const voices = isElevenLabsVoice(preferredVoiceURI) ? [] : await waitForVoices();
      const hindiVoiceOpts = {
        language: "hi" as const,
        ...(isElevenLabsVoice(preferredVoiceURI) ? { voiceId: "hi-IN-Neural2-A" } : {}),
      };

      setReviewHardWords(null);

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
        activateGlobal(sentence.globalStart);

        const tip = tipById.get(sentence.id) || null;
        setActiveTeach(tip);

        // 1) Read the story sentence in the lesson language
        const storyResult = await speakUtterance(sentence.text, voices, {
          keepAlive: true,
          onStart: () => activateGlobal(sentence.globalStart),
          onProgress: (elapsedMs, durationMs) => {
            if (!durationMs || !sentence.words.length) return;
            const i = Math.min(
              sentence.words.length - 1,
              Math.max(0, Math.floor((elapsedMs / durationMs) * sentence.words.length)),
            );
            activateGlobal(sentence.globalStart + i);
          },
        });
        if (cancelledRef.current || runIdRef.current !== runId) return;
        if (storyResult === "interrupted") return;

        await waitIfActive(350, runId);
        if (cancelledRef.current || runIdRef.current !== runId) return;

        // 2) Explain meaning only in Hindi (hard words come after the full story)
        const hindi =
          tip?.spoken_hi?.trim() ||
          tip?.meaning_hi?.trim() ||
          `इस वाक्य का आसान मतलब यह है: ${sentence.text}`;
        const explainResult = await speakUtterance(hindi, voices, {
          keepAlive: true,
          ...hindiVoiceOpts,
          onStart: () => activateGlobal(sentence.globalStart),
        });
        if (cancelledRef.current || runIdRef.current !== runId) return;
        if (explainResult === "interrupted") return;
        await waitIfActive(450, runId);
      }

      // 3) All hard words together at the end
      if (cancelledRef.current || runIdRef.current !== runId) return;
      const hardList = guide.all_hard_words?.length
        ? guide.all_hard_words
        : Array.from(
            new Map(
              (guide.sentences || [])
                .flatMap((row) => row.hard_words || [])
                .map((hw) => [hw.word.toLowerCase(), hw] as const),
            ).values(),
          );
      const hardSpoken =
        guide.hard_words_spoken_hi?.trim() ||
        (hardList.length
          ? `अब कहानी के मुश्किल शब्द समझते हैं। ${hardList
              .map((hw) => `${hw.word} का मतलब है: ${hw.meaning_hi}।`)
              .join(" ")}`
          : "");

      if (hardSpoken) {
        setActiveTeach(null);
        setReviewHardWords(hardList);
        await waitIfActive(500, runId);
        if (cancelledRef.current || runIdRef.current !== runId) return;
        const hardResult = await speakUtterance(hardSpoken, voices, {
          keepAlive: true,
          ...hindiVoiceOpts,
        });
        if (cancelledRef.current || runIdRef.current !== runId) return;
        if (hardResult === "interrupted") return;
      }

      if (runIdRef.current === runId) {
        finishPlayback(runId);
      }
    },
    [
      activateGlobal,
      ensureTeachGuide,
      finishPlayback,
      mode,
      paragraphs,
      preferredVoiceURI,
      sentences,
      setParagraphIndex,
      setPlaying,
      speakUtterance,
      waitIfActive,
      words.length,
    ],
  );

  /** One spoken word = one highlighted word. Cloud voices use continuous chunks instead. */
  const speakFromWord = useCallback(
    async (startWord: number) => {
      if (typeof window === "undefined") return;
      if (mode === "read") {
        setPlaying(true);
        return;
      }

      if (playbackStyle === "learn_hindi") {
        await speakLearnHindi(startWord);
        return;
      }

      let para = 0;
      for (let i = 0; i < paragraphs.length; i++) {
        if (startWord >= paragraphs[i].startWord) para = i;
      }

      // Cloud voices: continuous chunks (except Learn in Hindi, handled above)
      if (isElevenLabsVoice(preferredVoiceURI) && !skipElevenRef.current) {
        await speakDirect(para);
        return;
      }

      if (playbackStyle === "direct") {
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
      speakLearnHindi,
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
    setActiveTeach(null);
    setReviewHardWords(null);
    setPlaying(false);
  }, [setPlaying]);

  const play = () => {
    cancelWordPreview();
    primeElevenLabsPlayback();
    const elevenId = elevenLabsVoiceId(preferredVoiceURI);
    if (elevenId && !skipElevenRef.current) {
      const chunks = narrationChunks(paragraphIndex, 1100);
      if (chunks[0]) {
        prefetchElevenLabsAudio({
          text: chunks[0].text,
          voiceId: elevenId,
          speed,
          language: content.language,
        });
      }
    }
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

  useEffect(() => {
    teachCacheRef.current = null;
    setActiveTeach(null);
    setReviewHardWords(null);
    setTeachNote(null);
  }, [lessonId]);

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
        <button
          type="button"
          onClick={() => {
            stopAll();
            setActiveTeach(null);
            setReviewHardWords(null);
            setTeachNote(null);
            setPlaybackStyle("learn_hindi");
          }}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            playbackStyle === "learn_hindi" ? "bg-rose-600 text-white" : "bg-rose-50 text-rose-950",
          )}
        >
          Learn in Hindi
        </button>
      </div>

      {playbackStyle === "learn_hindi" ? (
        <div className="mb-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-3 text-sm text-rose-950">
          <p className="font-semibold">हिंदी में सीखो</p>
          <p className="mt-1 text-xs text-rose-900/80">
            Press Play: each sentence is read, then its meaning in simple Hindi. Hard words are
            explained together at the end.
          </p>
          {teachLoading ? <p className="mt-2 text-xs font-medium">Preparing Hindi help…</p> : null}
          {teachNote ? <p className="mt-2 text-xs text-rose-800">{teachNote}</p> : null}
          {activeTeach ? (
            <div className="mt-2 space-y-2">
              <p>
                <span className="font-semibold">Sentence:</span> {activeTeach.text}
              </p>
              <p>
                <span className="font-semibold">अर्थ:</span> {activeTeach.meaning_hi}
              </p>
            </div>
          ) : null}
          {reviewHardWords?.length ? (
            <div className="mt-2 space-y-2">
              <p className="font-semibold">मुश्किल शब्द (Hard words)</p>
              <ul className="list-disc space-y-1 pl-5 text-xs">
                {reviewHardWords.map((hw) => (
                  <li key={hw.word}>
                    <strong>{hw.word}</strong> — {hw.meaning_hi}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <p className="mb-1 text-xs font-semibold text-teal-800/80">Voice</p>
      <div className="mb-3 flex flex-wrap gap-2">
        {content.language !== "mr" || hasDeviceMarathi ? (
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
        ) : null}
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
          {content.language === "mr" ? "Marathi Google voice" : "Google voice"}
        </button>
      </div>
      {isElevenLabsVoice(preferredVoiceURI) && elevenVoices.length > 1 ? (
        <label className="mb-3 flex flex-col gap-1 text-sm text-teal-900">
          Google voice
          <select
            className="rounded-xl border border-teal-900/15 bg-white px-2 py-1.5"
            value={preferredVoiceURI ?? ""}
            onChange={(e) => {
              stopAll();
              skipElevenRef.current = false;
              setVoiceWarning(null);
              setPreferredVoiceURI(e.target.value || null);
            }}
            aria-label="Google voice"
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
              ? "Cloud Marathi voice — this phone’s Hindi voice will not be used."
              : "Google Cloud Text-to-Speech (falls back to Gemini TTS if needed)."}
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
      {!elevenEnabled && content.language !== "mr" ? (
        <p className="mb-3 text-xs text-amber-800">
          Google voice did not load. Add GOOGLE_TTS_API_KEY, then refresh.
        </p>
      ) : null}
      {content.language === "mr" && !hasDeviceMarathi && isElevenLabsVoice(preferredVoiceURI) ? (
        <p className="mb-3 text-xs text-teal-800/70">
          This phone has Hindi, not Marathi. Reading with a Marathi cloud voice.
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
