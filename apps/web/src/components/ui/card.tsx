import { cn } from "@/lib/utils";

export function Card({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-teal-900/10 bg-white/90 p-5 shadow-[0_10px_40px_-20px_rgba(15,80,70,0.35)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
