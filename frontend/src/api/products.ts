import { PRODUCTS_API_URL } from "../config";
import { parseApiResponse } from "../lib/http";
import type { Product, ProductPayload, Supplier } from "../types";

export type AuthorizedFetch = <T>(url: string, init?: RequestInit) => Promise<T>;

export function listProducts(fetcher: AuthorizedFetch) {
  return fetcher<Product[]>(`${PRODUCTS_API_URL}/products/`);
}

export function searchProducts(fetcher: AuthorizedFetch, name: string) {
  return fetcher<Product[]>(`${PRODUCTS_API_URL}/search_products/?name=${encodeURIComponent(name)}`);
}

export function getProduct(fetcher: AuthorizedFetch, productId: string) {
  return fetcher<Product>(`${PRODUCTS_API_URL}/products/${productId}`);
}

export function createProduct(fetcher: AuthorizedFetch, payload: ProductPayload) {
  return fetcher<Product>(`${PRODUCTS_API_URL}/products/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateProduct(fetcher: AuthorizedFetch, productId: string, payload: ProductPayload) {
  return fetcher<Product>(`${PRODUCTS_API_URL}/products/${productId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteProduct(fetcher: AuthorizedFetch, productId: string) {
  return fetcher<{ detail?: string }>(`${PRODUCTS_API_URL}/products/${productId}`, {
    method: "DELETE",
  });
}

export function listSuppliers(fetcher: AuthorizedFetch) {
  return fetcher<Supplier[]>(`${PRODUCTS_API_URL}/suppliers/`);
}

export async function uploadImage(accessToken: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${PRODUCTS_API_URL}/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: formData,
  });
  return parseApiResponse<{ imageUrl: string }>(response);
}
