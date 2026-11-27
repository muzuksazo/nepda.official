export interface GisCredentialResponse {
  credential: string;
  select_by?: string;
  clientId?: string;
}

export interface GisIdConfiguration {
  client_id: string;
  callback: (response: GisCredentialResponse) => void;
  auto_select?: boolean;
  cancel_on_tap_outside?: boolean;
  context?: 'signin' | 'signup' | 'use';
  itp_support?: boolean;
  use_fedcm_for_prompt?: boolean;
}

export interface GisButtonConfiguration {
  type?: 'standard' | 'icon';
  theme?: 'outline' | 'filled_blue' | 'filled_black';
  size?: 'large' | 'medium' | 'small';
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
  shape?: 'rectangular' | 'pill' | 'circle' | 'square';
  logo_alignment?: 'left' | 'center';
  width?: number;
  locale?: string;
}

export interface GisPromptMomentNotification {
  isDisplayMoment: () => boolean;
  isDisplayed: () => boolean;
  isNotDisplayed: () => boolean;
  getNotDisplayedReason: () => string;
  isSkippedMoment: () => boolean;
  getSkippedReason: () => string;
  isDismissedMoment: () => boolean;
  getDismissedReason: () => string;
}

export interface GisAccountsId {
  initialize: (config: GisIdConfiguration) => void;
  prompt: (momentListener?: (notification: GisPromptMomentNotification) => void) => void;
  renderButton: (parent: HTMLElement, options: GisButtonConfiguration) => void;
  disableAutoSelect: () => void;
  cancel: () => void;
  revoke: (hint: string, callback?: (done: { successful: boolean; error?: string }) => void) => void;
}

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: GisAccountsId;
      };
    };
  }
}

export const GIS_SCRIPT_SRC = 'https://accounts.google.com/gsi/client';

let scriptPromise: Promise<GisAccountsId> | null = null;
let initializedClientId: string | null = null;
let activeCredentialHandler: ((credential: string) => void) | null = null;

export function getGoogleClientId(): string {
  return (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim() ?? '';
}

export function loadGisScript(): Promise<GisAccountsId> {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return Promise.reject(new Error('Google Identity Services requires a browser environment.'));
  }

  const existing = window.google?.accounts?.id;
  if (existing) {
    return Promise.resolve(existing);
  }

  if (scriptPromise) {
    return scriptPromise;
  }

  scriptPromise = new Promise<GisAccountsId>((resolve, reject) => {
    const finish = () => {
      const gis = window.google?.accounts?.id;
      if (gis) {
        resolve(gis);
      } else {
        scriptPromise = null;
        reject(new Error('Google Identity Services loaded without accounts.id.'));
      }
    };

    const fail = () => {
      scriptPromise = null;
      reject(new Error('Failed to load Google Identity Services script.'));
    };

    const found = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SCRIPT_SRC}"]`);
    if (found) {
      found.addEventListener('load', finish, { once: true });
      found.addEventListener('error', fail, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = GIS_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener('load', finish, { once: true });
    script.addEventListener('error', fail, { once: true });
    document.head.appendChild(script);
  });

  return scriptPromise;
}

export async function initializeGis(
  clientId: string,
  onCredential: (credential: string) => void,
): Promise<GisAccountsId> {
  activeCredentialHandler = onCredential;
  const gis = await loadGisScript();

  if (initializedClientId !== clientId) {
    gis.initialize({
      client_id: clientId,
      callback: (response) => {
        if (response.credential) {
          activeCredentialHandler?.(response.credential);
        }
      },
      auto_select: false,
      cancel_on_tap_outside: true,
      use_fedcm_for_prompt: true,
    });
    initializedClientId = clientId;
  }

  return gis;
}
