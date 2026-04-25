import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import * as authApi from "../api/auth";
import { ApiError, parseApiResponse } from "../lib/http";
import type { CurrentUser } from "../types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: CurrentUser | null;
  accessToken: string | null;
  canWriteProducts: boolean;
  login: (email: string, password: string, rememberMe: boolean) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<string | null>;
  authorizedFetch: <T>(url: string, init?: RequestInit) => Promise<T>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const refreshPromise = useRef<Promise<string | null> | null>(null);

  const loadUser = useCallback(async (token: string) => {
    const currentUser = await authApi.getMe(token);
    setUser(currentUser);
    setStatus("authenticated");
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const refreshAccessToken = useCallback(async () => {
    if (!refreshPromise.current) {
      refreshPromise.current = authApi
        .refreshToken()
        .then(async (data) => {
          if (!data.access_token) {
            clearSession();
            return null;
          }
          setAccessToken(data.access_token);
          await loadUser(data.access_token);
          return data.access_token;
        })
        .catch(() => {
          clearSession();
          return null;
        })
        .finally(() => {
          refreshPromise.current = null;
        });
    }

    return refreshPromise.current;
  }, [clearSession, loadUser]);

  useEffect(() => {
    void refreshAccessToken();
  }, [refreshAccessToken]);

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean) => {
      const data = await authApi.login(email, password, rememberMe);
      setAccessToken(data.access_token);
      await loadUser(data.access_token);
    },
    [loadUser],
  );

  const register = useCallback(async (name: string, email: string, password: string) => {
    await authApi.register(name, email, password);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const authorizedFetch = useCallback(
    async <T,>(url: string, init: RequestInit = {}) => {
      let token = accessToken || (await refreshAccessToken());
      if (!token) {
        throw new ApiError("Unauthorized", 401);
      }

      const makeRequest = (requestToken: string) =>
        fetch(url, {
          ...init,
          headers: {
            ...init.headers,
            Authorization: `Bearer ${requestToken}`,
          },
        });

      let response = await makeRequest(token);
      if (response.status === 401) {
        token = await refreshAccessToken();
        if (!token) {
          throw new ApiError("Unauthorized", 401);
        }
        response = await makeRequest(token);
      }

      return parseApiResponse<T>(response);
    },
    [accessToken, refreshAccessToken],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      accessToken,
      canWriteProducts: user?.role === "operator" || user?.role === "admin",
      login,
      register,
      logout,
      refreshAccessToken,
      authorizedFetch,
    }),
    [accessToken, authorizedFetch, login, logout, refreshAccessToken, register, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
