"use client";

import { FormEvent } from "react";
import { ArrowUp } from "lucide-react";
import { PaviMicButton } from "@/components/pavi/PaviMicButton";
import type { MicState } from "@/lib/speech-providers";
import { cn } from "@/lib/utils";

export function PaviInput({
  value,
  onChange,
  onSubmit,
  onMic,
  micState,
  disabled,
  placeholder = "Ask Pavi…",
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onMic: () => void;
  micState: MicState;
  disabled?: boolean;
  placeholder?: string;
}) {
  function handle(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }
  const listening = micState === "listening";
  return (
    <form onSubmit={handle} className="w-full">
      <div
        className={cn(
          "flex items-center gap-2 rounded-full border bg-white px-2 py-1.5 shadow-[0_10px_30px_-18px_rgba(15,80,70,0.45)] transition",
          listening ? "border-teal-500 ring-4 ring-teal-500/10" : "border-teal-900/10",
        )}
      >
        <PaviMicButton state={micState} onClick={onMic} disabled={disabled} />
        <label className="sr-only" htmlFor="pavi-input">
          Message Pavi
        </label>
        <input
          id="pavi-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={listening ? "Listening…" : placeholder}
          disabled={disabled}
          className="h-11 min-w-0 flex-1 bg-transparent text-[15px] text-teal-950 outline-none placeholder:text-teal-900/35"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Send"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#0f4f4a] text-white transition hover:bg-teal-900 disabled:bg-teal-900/20 disabled:text-white/70"
        >
          <ArrowUp className="h-5 w-5" />
        </button>
      </div>
    </form>
  );
}
