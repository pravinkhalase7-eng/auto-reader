"use client";

import { PaviAvatar } from "@/components/pavi/PaviAvatar";

export function PaviTypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <PaviAvatar size="sm" speaking />
      <div className="flex items-center gap-1 rounded-[22px] rounded-bl-md bg-[#f4f7f5] px-4 py-3">
        <span className="sr-only">Pavi is thinking</span>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal-700/70"
            style={{ animationDelay: `${i * 0.12}s` }}
          />
        ))}
      </div>
    </div>
  );
}
