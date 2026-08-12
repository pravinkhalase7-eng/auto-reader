import { cn } from "@/lib/utils";

const LANGUAGE_LABELS: Record<string, string> = {
  en: "English",
  hi: "हिन्दी",
  mr: "मराठी",
};

export function LanguageBadge({ code, className }: { code: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-900",
        className,
      )}
    >
      {LANGUAGE_LABELS[code] || code}
    </span>
  );
}

export function ContentTypeBadge({ type, className }: { type: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-950 capitalize",
        className,
      )}
    >
      {type}
    </span>
  );
}
