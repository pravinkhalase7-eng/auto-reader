"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { clearToken, setToken } from "@/lib/api";

type AuthState = {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  setUser: (user: User | null) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (user, token) => {
        setToken(token);
        set({ user, token });
      },
      setUser: (user) => set({ user }),
      logout: () => {
        clearToken();
        set({ user: null, token: null });
      },
    }),
    {
      name: "ai-teacher-auth",
      onRehydrateStorage: () => (state) => {
        if (state?.token) setToken(state.token);
      },
    },
  ),
);
