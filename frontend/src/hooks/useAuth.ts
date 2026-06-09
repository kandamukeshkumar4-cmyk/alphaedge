"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ACCESS_TOKEN_KEY } from "@/lib/portfolio-api";

export const USER_EMAIL_KEY = "alphaedge.userEmail";

export function saveAuthSession(accessToken: string, userEmail: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(USER_EMAIL_KEY, userEmail);
}

export function useAuth() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem(ACCESS_TOKEN_KEY));
    setEmail(localStorage.getItem(USER_EMAIL_KEY));
    setIsReady(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
    setToken(null);
    setEmail(null);
    router.replace("/auth/login");
  }, [router]);

  return { token, email, logout, isReady };
}
