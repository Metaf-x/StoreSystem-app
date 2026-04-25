export const AUTH_API_URL =
  import.meta.env.VITE_AUTH_API_URL?.replace(/\/$/, "") || "http://localhost:8001";

export const PRODUCTS_API_URL =
  import.meta.env.VITE_PRODUCTS_API_URL?.replace(/\/$/, "") || "http://localhost:8002";
