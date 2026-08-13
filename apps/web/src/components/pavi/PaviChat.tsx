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
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  if (!messages.length && !typing) {
    return <div className="flex flex-1 flex-col items-center justify-center px-4 py-6">{emptyState}</div>;
  }

  return (
    <div className="pavi-scroll flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4 md:px-6">
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
      <div ref={endRef} />
    </div>
  );
}
