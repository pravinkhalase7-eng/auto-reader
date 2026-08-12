"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BookOpen, Home, LogOut, Upload, User } from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/lessons", label: "Lessons", icon: BookOpen },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/profile", label: "Profile", icon: User },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-teal-900/10 bg-[#f3f7f4]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/dashboard" className="font-display text-xl font-bold tracking-tight text-teal-950">
            AI Teacher
          </Link>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {links.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-teal-900/70 hover:bg-teal-900/5 hover:text-teal-950",
                  pathname.startsWith(href) && "bg-teal-900/10 text-teal-950",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <span className="hidden text-sm text-teal-900/70 sm:inline">{user?.full_name}</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Sign out"
              onClick={() => {
                logout();
                router.push("/");
              }}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <nav className="flex justify-around border-t border-teal-900/5 px-2 py-2 md:hidden" aria-label="Mobile">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center gap-1 rounded-lg px-3 py-1 text-[11px] font-medium text-teal-900/60",
                pathname.startsWith(href) && "text-teal-800",
              )}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 md:py-10">{children}</main>
    </div>
  );
}
