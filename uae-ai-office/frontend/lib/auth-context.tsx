"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { authApi, ApiError, registerUnauthorizedHandler, setAccessToken, tenancyApi } from "./api-client";
import type { CompanyPublic, Role, UserPublic } from "./types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: UserPublic | null;
  companyId: string | null;
  company: CompanyPublic | null;
  role: Role | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  signup: (data: { email: string; password: string; full_name: string; company_name: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshCompany: () => Promise<void>;
  switchCompany: (companyId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadAuthenticatedState(): Promise<AuthState> {
  const [me, currentCompany] = await Promise.all([
    authApi.me(),
    tenancyApi.getCurrentCompany().catch(() => null),
  ]);
  return {
    status: "authenticated",
    user: me.user,
    companyId: me.company_id,
    company: currentCompany?.company ?? null,
    role: me.role,
  };
}

const UNAUTHENTICATED_STATE: AuthState = {
  status: "unauthenticated",
  user: null,
  companyId: null,
  company: null,
  role: null,
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
    companyId: null,
    company: null,
    role: null,
  });

  useEffect(() => {
    registerUnauthorizedHandler(() => {
      setState(UNAUTHENTICATED_STATE);
      router.replace("/login");
    });
    return () => registerUnauthorizedHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const refreshed = await authApi.refresh();
      if (!refreshed) {
        if (!cancelled) setState(UNAUTHENTICATED_STATE);
        return;
      }
      try {
        const nextState = await loadAuthenticatedState();
        if (!cancelled) setState(nextState);
      } catch {
        if (!cancelled) setState(UNAUTHENTICATED_STATE);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokenResponse = await authApi.login({ email, password });
    setAccessToken(tokenResponse.access_token);
    setState(await loadAuthenticatedState());
  }, []);

  const signup = useCallback(
    async (data: { email: string; password: string; full_name: string; company_name: string }) => {
      const tokenResponse = await authApi.signup(data);
      setAccessToken(tokenResponse.access_token);
      setState(await loadAuthenticatedState());
    },
    []
  );

  const logout = useCallback(async () => {
    await authApi.logout();
    setAccessToken(null);
    setState(UNAUTHENTICATED_STATE);
    router.replace("/login");
  }, [router]);

  const refreshCompany = useCallback(async () => {
    const currentCompany = await tenancyApi.getCurrentCompany().catch(() => null);
    if (currentCompany) {
      setState((prev) => ({ ...prev, company: currentCompany.company, role: currentCompany.role }));
    }
  }, []);

  const switchCompany = useCallback(async (companyId: string) => {
    const tokenResponse = await authApi.switchCompany(companyId);
    setAccessToken(tokenResponse.access_token);
    setState(await loadAuthenticatedState());
  }, []);

  const value = useMemo(
    () => ({ ...state, login, signup, logout, refreshCompany, switchCompany }),
    [state, login, signup, logout, refreshCompany, switchCompany]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function isForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403;
}

export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof ApiError) {
    if (error.code === "validation_error" && error.details?.length) {
      return error.details.map((d) => d.msg).join(" ");
    }
    return error.message;
  }
  return fallback;
}

