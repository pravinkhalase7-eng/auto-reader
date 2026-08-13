"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { PaviMessage } from "@/components/pavi/PaviMessage";
import { PaviTypingIndicator } from "@/components/pavi/PaviTypingIndicator";
import { PaviConfirmationCard } from "@/components/pavi/PaviConfirmationCard";
import type { PaviConfirmation } from "@/types/pavi";

export type ChatLine = {
  id: string;
  role: string;
  content: string;
  confirmation?: PaviConfirmation | null;
};

export function PaviChat({
  messages,
  typing,
  emptyState,
}: {
  messages: ChatLine[];
  typing?: boolean;
  emptyState?: ReactNode;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, typing]);

  const empty = !messages.length && !typing;

  return (
    <div ref={scrollerRef} className="pavi-scroll min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
      {empty ? (
        <div className="flex min-h-full flex-col items-center justify-center px-4 py-6">{emptyState}</div>
      ) : (
        <div className="flex flex-col gap-3 px-4 py-4 md:px-6">
          {messages.map((m) => (
            <div key={m.id} className="space-y-2">
              <PaviMessage role={m.role} content={m.content} />
              {m.confirmation && <PaviConfirmationCard confirmation={m.confirmation} />}
            </div>
          ))}
          {typing && (
            <div className="flex justify-start">
              <PaviTypingIndicator />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
