"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";

export function useAuthHydrated() {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const finish = () => setHydrated(true);
    if (useAuthStore.persist.hasHydrated()) finish();
    return useAuthStore.persist.onFinishHydration(finish);
  }, []);
  return hydrated;
}

/** Wait for localStorage auth to restore before sending anyone to /login. */
export function useRequireAuth() {
  const router = useRouter();
  const pathname = usePathname();
  const token = useAuthStore((s) => s.token);
  const hydrated = useAuthHydrated();

  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      const next = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [hydrated, token, pathname, router]);

  return { token, ready: hydrated && Boolean(token), hydrated };
}
