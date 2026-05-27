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
  let lastError: Error | null = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { ...headers, ...init?.headers },
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        if (attempt === 0 && res.status >= 500) {
          await new Promise((r) => setTimeout(r, 1000));
          continue;
        }
        console.error(`API error: ${res.status} ${path}`, body);
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
      }
      return res.json();
    } catch (e) {
      lastError = e instanceof Error ? e : new Error(String(e));
      if (attempt === 0 && !lastError.message.startsWith("API ")) {
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      throw lastError;
    }
  }
  throw lastError!;
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
