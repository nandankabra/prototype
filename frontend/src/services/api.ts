import { useCallback, useEffect, useState } from 'react';
const tokenKey = 'bytecode-session';
export const getToken = () => sessionStorage.getItem(tokenKey);
export const setToken = (value: string | null) => value ? sessionStorage.setItem(tokenKey, value) : sessionStorage.removeItem(tokenKey);
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (getToken()) headers.set('Authorization', `Bearer ${getToken()}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: 'The service could not be reached' }));
    const message = typeof data.detail === 'string' ? data.detail : data.detail?.map((d: {msg: string}) => d.msg).join('; ');
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json();
}
export const post = <T,>(path: string, data: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(data) });
export async function fileBlob(path: string): Promise<Blob> {
  const response = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!response.ok) throw new Error('The document could not be downloaded');
  return response.blob();
}
export async function download(path: string, filename: string) {
  const blob = await fileBlob(path); const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function useApi<T>(path: string, pollMs = 0) {
  const [data, setData] = useState<T | null>(null), [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try { const result = await request<T>(path); setData(result); setError(''); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => { setData(null); setLoading(true); void reload(); if (pollMs) { const id = setInterval(reload, pollMs); return () => clearInterval(id); } }, [reload, pollMs]);
  return { data, error, loading, reload, setData };
}
