import { getIdToken } from "./firebase";

const API_BASE = "/api";

async function authHeaders(): Promise<HeadersInit> {
  const token = await getIdToken();
  if (!token) throw new Error("Not authenticated — please sign in again");
  return { Authorization: `Bearer ${token}` };
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...headers, ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    console.error(`API error: ${res.status} ${path}`, body);
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export async function apiPost<T>(
  path: string,
  body: FormData | Record<string, unknown>,
): Promise<T> {
  const headers = await authHeaders();
  const isFormData = body instanceof FormData;
  return apiFetch<T>(path, {
    method: "POST",
    headers: isFormData ? headers : { ...headers, "Content-Type": "application/json" },
    body: isFormData ? body : JSON.stringify(body),
  });
}
