export interface ApiErrorPayload {
  detail?:
    | string
    | {
        error?: {
          code?: string;
          message?: string;
          details?: Record<string, unknown>;
        };
      };
}

export class NapdaApiError extends Error {
  status: number;
  code: string | undefined;
  details: Record<string, unknown> | undefined;
  rawBody: unknown;

  constructor(
    status: number,
    message: string,
    code?: string,
    details?: Record<string, unknown>,
    rawBody?: unknown,
  ) {
    super(message);
    this.name = "NapdaApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.rawBody = rawBody;
  }
}

let configuredBaseUrl: string | undefined;
let configuredAccessToken: string | undefined;

export function setApiBaseUrl(url: string): void {
  configuredBaseUrl = url.replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  if (configuredBaseUrl !== undefined) {
    return configuredBaseUrl;
  }
  const envUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return envUrl ? envUrl.replace(/\/+$/, "") : "";
}

export function setAccessToken(token: string | undefined): void {
  configuredAccessToken = token;
}

export function getAccessToken(): string | undefined {
  return configuredAccessToken;
}

function buildUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  const base = getApiBaseUrl();
  if (!base) {
    return url;
  }
  return url.startsWith("/") ? `${base}${url}` : `${base}/${url}`;
}

export async function customFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const headers = new Headers(options?.headers);
  if (configuredAccessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${configuredAccessToken}`);
  }

  const response = await fetch(buildUrl(url), {
    ...options,
    headers,
    credentials: options?.credentials ?? "include",
  });

  if (response.status === 204) {
    return {
      data: undefined,
      status: response.status,
      headers: response.headers,
    } as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const rawText = await response.text();
  let parsed: unknown = undefined;
  if (rawText) {
    if (contentType.includes("application/json")) {
      try {
        parsed = JSON.parse(rawText);
      } catch {
        parsed = rawText;
      }
    } else {
      parsed = rawText;
    }
  }

  if (!response.ok) {
    const payload = (typeof parsed === "object" && parsed !== null
      ? parsed
      : undefined) as ApiErrorPayload | undefined;
    const nested =
      typeof payload?.detail === "object" && payload.detail !== null
        ? payload.detail.error
        : undefined;
    const message =
      nested?.message ??
      (typeof payload?.detail === "string" ? payload.detail : undefined) ??
      `HTTP ${response.status}`;
    throw new NapdaApiError(
      response.status,
      message,
      nested?.code,
      nested?.details,
      parsed,
    );
  }

  return {
    data: parsed,
    status: response.status,
    headers: response.headers,
  } as T;
}
