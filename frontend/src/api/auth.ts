import { AUTH_API_URL } from "../config";
import type { CurrentUser, LoginResponse, RefreshTokenResponse } from "../types";
import { parseApiResponse } from "../lib/http";

export async function login(email: string, password: string, rememberMe: boolean) {
  const response = await fetch(`${AUTH_API_URL}/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, remember_me: rememberMe }),
  });
  return parseApiResponse<LoginResponse>(response);
}

export async function register(name: string, email: string, password: string) {
  const response = await fetch(`${AUTH_API_URL}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  return parseApiResponse(response);
}

export async function refreshToken() {
  const response = await fetch(`${AUTH_API_URL}/refresh-token`, {
    method: "POST",
    credentials: "include",
  });
  return parseApiResponse<RefreshTokenResponse>(response);
}

export async function logout() {
  const response = await fetch(`${AUTH_API_URL}/logout`, {
    method: "POST",
    credentials: "include",
  });
  return parseApiResponse<{ detail: string }>(response);
}

export async function getMe(accessToken: string) {
  const response = await fetch(`${AUTH_API_URL}/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return parseApiResponse<CurrentUser>(response);
}
