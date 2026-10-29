const TOKEN_KEY = 'xc_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(extra) {
  const token = getToken();
  const headers = { ...(extra || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: authHeaders({
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      message = JSON.parse(text).detail || text;
    } catch {
      /* keep raw text */
    }
    const error = new Error(message || `请求失败 (${res.status})`);
    error.status = res.status;
    throw error;
  }

  return res.json();
}
