export function apiHeaders(token = process.env.NEXT_PUBLIC_DEMO_API_TOKEN): Headers {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const authorization = apiHeaders().get("Authorization");
  if (authorization) headers.set("Authorization", authorization);
  return fetch(input, { ...init, headers });
}
