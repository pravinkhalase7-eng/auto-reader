"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, LayoutDashboard } from "lucide-react";
import { PaviAvatar } from "@/components/pavi/PaviAvatar";
import { PaviChat, type ChatLine } from "@/components/pavi/PaviChat";
import { PaviInput } from "@/components/pavi/PaviInput";
import { ReminderCard } from "@/components/pavi/ReminderCard";
import { AppointmentCard } from "@/components/pavi/AppointmentCard";
import { getSpeechProvider, type MicState } from "@/lib/speech-providers";
import { getAppointments, getConversations, getUpcomingReminders, sendChatMessage, sendVoiceTranscript } from "@/lib/pavi-api";
import { ApiError } from "@/lib/api";

const SUGGESTIONS = [
  "Create an appointment for 4pm",
  "Remind me tomorrow at 8am to take medicines",
  "What do I have today?",
];

let lineId = 0;
function nid() {
  lineId += 1;
  return `local-${lineId}`;
}

export function PaviAssistant() {
  const queryClient = useQueryClient();
  const speech = useMemo(() => getSpeechProvider(), []);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatLine[]>([]);
  const [micState, setMicState] = useState<MicState>("idle");
  const [micError, setMicError] = useState<string | null>(null);
  const [interim, setInterim] = useState("");

  const reminders = useQuery({ queryKey: ["pavi-reminders-upcoming"], queryFn: getUpcomingReminders });
  const appointments = useQuery({ queryKey: ["pavi-appointments"], queryFn: getAppointments });
  const conversations = useQuery({ queryKey: ["pavi-conversations"], queryFn: getConversations });

  const chat = useMutation({
    mutationFn: async ({ text, voice }: { text: string; voice?: boolean }) => {
      if (voice) return sendVoiceTranscript(text, conversationId);
      return sendChatMessage(text, conversationId);
    },
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { id: nid(), role: "assistant", content: data.message, confirmation: data.confirmation },
      ]);
      queryClient.invalidateQueries({ queryKey: ["pavi-reminders-upcoming"] });
      queryClient.invalidateQueries({ queryKey: ["pavi-appointments"] });
      queryClient.invalidateQueries({ queryKey: ["pavi-schedule"] });
      queryClient.invalidateQueries({ queryKey: ["pavi-conversations"] });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : "I couldn't save that reminder right now. Please try again.";
      setMessages((prev) => [...prev, { id: nid(), role: "assistant", content: msg }]);
    },
  });

  function send(text: string, voice = false) {
    const trimmed = text.trim();
    if (!trimmed || chat.isPending) return;
    setMessages((prev) => [...prev, { id: nid(), role: "user", content: trimmed }]);
    setInput("");
    setInterim("");
    chat.mutate({ text: trimmed, voice });
  }

  async function onMic() {
    if (micState === "listening") {
      speech.stop();
      setMicState("idle");
      return;
    }
    if (!speech.isSupported()) {
      setMicState("error");
      setMicError("Voice input isn’t available in this browser. You can still type to Pavi.");
      return;
    }
    setMicError(null);
    setMicState("requesting_permission");
    try {
      await speech.start(
        (transcript, isFinal) => {
          setInterim(transcript);
          setInput(transcript);
          if (isFinal) {
            setMicState("processing");
            speech.stop();
            send(transcript, true);
            setMicState("idle");
          }
        },
        (message) => {
          setMicState("error");
          setMicError(message);
        },
        () => {
          setMicState((s) => (s === "listening" ? "idle" : s));
        },
      );
      setMicState("listening");
    } catch {
      setMicState("error");
      setMicError("Microphone permission is needed to talk to Pavi.");
    }
  }

  const listening = micState === "listening";
  const hasThread = messages.length > 0;

  return (
    <div className="grid h-[calc(100vh-7.5rem)] gap-4 lg:grid-cols-[minmax(0,1fr)_280px] lg:h-[calc(100vh-6rem)]">
      <section className="flex min-h-0 flex-col overflow-hidden rounded-[1.75rem] border border-white/70 bg-white/80 shadow-[0_20px_60px_-32px_rgba(15,80,70,0.45)] backdrop-blur-sm">
        <header className="flex items-center gap-3 border-b border-teal-900/6 px-4 py-3 md:px-5">
          <PaviAvatar listening={listening} speaking={chat.isPending} size="md" />
          <div className="min-w-0 flex-1">
            <p className="font-display text-lg font-semibold leading-tight text-teal-950">Pavi</p>
            <p className="text-xs text-teal-800/60">
              {listening ? "Listening…" : chat.isPending ? "Thinking…" : "Your AI assistant"}
            </p>
          </div>
          <Link
            href="/pavi/dashboard"
            className="rounded-full px-3 py-1.5 text-xs font-medium text-teal-800/70 hover:bg-teal-900/5 lg:hidden"
          >
            Schedule
          </Link>
        </header>

        <PaviChat
          messages={messages}
          typing={chat.isPending}
          emptyState={
            <div className="mx-auto max-w-md text-center">
              <PaviAvatar listening={listening} speaking={chat.isPending} size="lg" />
              <h1 className="font-display mt-5 text-3xl font-semibold text-teal-950">Hi, I&apos;m Pavi</h1>
              <p className="mt-2 text-teal-800/70">How can I help you today? Times are in IST.</p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="rounded-full border border-teal-900/10 bg-white px-3.5 py-2 text-left text-sm text-teal-900/80 shadow-sm transition hover:border-teal-700/30 hover:text-teal-950"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          }
        />

        <div className="border-t border-teal-900/6 px-4 py-3 md:px-5">
          {listening && interim && (
            <p className="mb-2 truncate px-2 text-center text-sm text-teal-800/70">“{interim}”</p>
          )}
          {micError && <p className="mb-2 px-2 text-center text-sm text-rose-700">{micError}</p>}
          <PaviInput
            value={input}
            onChange={setInput}
            onSubmit={() => send(input)}
            onMic={onMic}
            micState={micState}
            disabled={chat.isPending}
            placeholder={hasThread ? "Message Pavi…" : "Press the mic or type a reminder…"}
          />
        </div>
      </section>

      <aside className="hidden min-h-0 flex-col gap-4 overflow-y-auto lg:flex">
        <div className="flex gap-2">
          <Link
            href="/pavi/dashboard"
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-teal-900/10 bg-white/80 px-3 py-2 text-xs font-medium text-teal-900/80 hover:bg-white"
          >
            <LayoutDashboard className="h-3.5 w-3.5" /> Dashboard
          </Link>
          <Link
            href="/pavi/reminders/new"
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-teal-900/10 bg-white/80 px-3 py-2 text-xs font-medium text-teal-900/80 hover:bg-white"
          >
            <CalendarPlus className="h-3.5 w-3.5" /> New reminder
          </Link>
        </div>
        <section className="rounded-2xl border border-white/70 bg-white/70 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-teal-800/50">Upcoming</h2>
          <div className="space-y-2.5">
            {(reminders.data || []).slice(0, 4).map((r) => (
              <ReminderCard key={r.id} reminder={r} />
            ))}
            {!reminders.data?.length && <p className="text-sm text-teal-800/50">No reminders yet.</p>}
          </div>
        </section>
        <section className="rounded-2xl border border-white/70 bg-white/70 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-teal-800/50">Appointments</h2>
          <div className="space-y-2.5">
            {(appointments.data || []).slice(0, 3).map((a) => (
              <AppointmentCard key={a.id} appointment={a} />
            ))}
            {!appointments.data?.length && <p className="text-sm text-teal-800/50">None scheduled.</p>}
          </div>
        </section>
        <section className="rounded-2xl border border-white/70 bg-white/70 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-teal-800/50">Recent</h2>
          <ul className="space-y-2 text-sm">
            {(conversations.data || []).slice(0, 5).map((c) => (
              <li key={c.id} className="truncate text-teal-800/75">
                {c.title}
              </li>
            ))}
            {!conversations.data?.length && <li className="text-teal-800/50">Start by saying hello.</li>}
          </ul>
        </section>
      </aside>
    </div>
  );
}
