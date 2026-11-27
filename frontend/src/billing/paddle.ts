export type PaddleEnvironmentMode = 'sandbox' | 'production';

export interface PaddleCheckoutEvent {
  name?: string;
  data?: {
    transaction_id?: string;
    status?: string;
    [key: string]: unknown;
  };
  error?: {
    code?: string;
    detail?: string;
    message?: string;
  };
}

interface PaddleGlobal {
  Environment?: {
    set: (env: PaddleEnvironmentMode) => void;
  };
  Initialize: (options: {
    token: string;
    eventCallback?: (event: PaddleCheckoutEvent) => void;
  }) => void;
  Checkout: {
    open: (options: {
      transactionId: string;
      customer?: { email?: string };
      settings?: {
        displayMode?: 'overlay' | 'inline';
        theme?: 'light' | 'dark';
        locale?: string;
      };
    }) => void;
  };
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

export interface OpenPaddleCheckoutOptions {
  environment: PaddleEnvironmentMode;
  clientToken: string;
  transactionId: string;
  customerEmail?: string | null;
  theme?: 'light' | 'dark';
  onCompleted?: (transactionId?: string) => void;
  onClosed?: () => void;
  onError?: (message: string) => void;
}

const PADDLE_SCRIPT_SRC = 'https://cdn.paddle.com/paddle/v2/paddle.js';

let scriptPromise: Promise<PaddleGlobal> | null = null;
let initializedKey: string | null = null;
let activeSession: {
  didComplete: boolean;
  onCompleted?: (transactionId?: string) => void;
  onClosed?: () => void;
  onError?: (message: string) => void;
} | null = null;

function handlePaddleEvent(event: PaddleCheckoutEvent): void {
  const session = activeSession;
  if (!session) return;

  if (event.name === 'checkout.completed') {
    session.didComplete = true;
    const txnId = event.data?.transaction_id;
    const cb = session.onCompleted;
    activeSession = null;
    cb?.(txnId);
    return;
  }

  if (event.name === 'checkout.error') {
    const msg =
      event.error?.detail ??
      event.error?.message ??
      '결제창 처리 중 오류가 발생했어요.';
    const cb = session.onError;
    activeSession = null;
    cb?.(msg);
    return;
  }

  if (event.name === 'checkout.closed') {
    if (!session.didComplete) {
      const cb = session.onClosed;
      activeSession = null;
      cb?.();
    } else {
      activeSession = null;
    }
  }
}

export function loadPaddleJs(): Promise<PaddleGlobal> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Paddle.js는 브라우저 환경에서만 사용할 수 있어요.'));
  }
  if (window.Paddle) {
    return Promise.resolve(window.Paddle);
  }
  if (scriptPromise) {
    return scriptPromise;
  }

  scriptPromise = new Promise<PaddleGlobal>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${PADDLE_SCRIPT_SRC}"]`,
    );
    const finish = () => {
      if (window.Paddle) {
        resolve(window.Paddle);
      } else {
        scriptPromise = null;
        reject(new Error('Paddle.js가 로드되지 않았어요.'));
      }
    };

    if (existing) {
      existing.addEventListener('load', finish, { once: true });
      existing.addEventListener(
        'error',
        () => {
          scriptPromise = null;
          reject(new Error('Paddle 결제 스크립트를 불러오지 못했어요.'));
        },
        { once: true },
      );
      return;
    }

    const script = document.createElement('script');
    script.src = PADDLE_SCRIPT_SRC;
    script.async = true;
    script.onload = finish;
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error('Paddle 결제 스크립트를 불러오지 못했어요.'));
    };
    document.head.appendChild(script);
  });

  return scriptPromise;
}

export async function openPaddleCheckout(
  options: OpenPaddleCheckoutOptions,
): Promise<void> {
  const paddle = await loadPaddleJs();
  const key = `${options.environment}:${options.clientToken}`;
  if (initializedKey !== key) {
    if (options.environment === 'sandbox') {
      paddle.Environment?.set('sandbox');
    }
    paddle.Initialize({
      token: options.clientToken,
      eventCallback: handlePaddleEvent,
    });
    initializedKey = key;
  }

  activeSession = {
    didComplete: false,
    onCompleted: options.onCompleted,
    onClosed: options.onClosed,
    onError: options.onError,
  };

  paddle.Checkout.open({
    transactionId: options.transactionId,
    customer: options.customerEmail ? { email: options.customerEmail } : undefined,
    settings: {
      displayMode: 'overlay',
      theme: options.theme ?? 'light',
      locale: 'ko',
    },
  });
}
