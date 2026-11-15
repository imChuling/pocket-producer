// Demo list data is exported as static files (backend/scripts/export_demo_snapshot.py)
// so browsing the demo does not start a backend instance. The API stays as a
// fallback for a snapshot that has not been exported yet.

export async function loadDemo<T>(name: string, apiPath: string): Promise<T> {
  try {
    const res = await fetch(`/demo-data/${name}.json`);
    if (res.ok) return (await res.json()) as T;
  } catch {
    // fall through to the API
  }
  const res = await fetch(`/api/demo/${apiPath}`);
  if (!res.ok) throw new Error(`demo ${apiPath}: ${res.status}`);
  return (await res.json()) as T;
}
