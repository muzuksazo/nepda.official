export interface ScenarioAbOverride {
  provider?: 'anthropic' | 'google';
  model?: string;
}

const PROVIDER_KEY = 'napda_ab_provider';
const MODEL_KEY = 'napda_ab_model';

function inferProviderFromModel(model: string): 'anthropic' | 'google' {
  return /^gemini/i.test(model.trim()) ? 'google' : 'anthropic';
}

export function readScenarioAbOverride(
  search?: string,
  storage?: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null,
): ScenarioAbOverride {
  const rawSearch = search ?? (typeof window !== 'undefined' ? window.location.search : '');
  const store = storage === undefined ? (typeof window !== 'undefined' ? window.sessionStorage : null) : storage;

  const params = new URLSearchParams(rawSearch);
  const qProvider = params.get('provider')?.trim().toLowerCase();
  const qModel = params.get('model')?.trim();

  if (qProvider === 'auto' || qProvider === 'reset') {
    store?.removeItem(PROVIDER_KEY);
    store?.removeItem(MODEL_KEY);
    return {};
  }

  if (qProvider === 'anthropic' || qProvider === 'google') {
    store?.setItem(PROVIDER_KEY, qProvider);
  }

  if (qModel) {
    if (qModel.toLowerCase() === 'auto' || qModel.toLowerCase() === 'reset') {
      store?.removeItem(MODEL_KEY);
    } else {
      store?.setItem(MODEL_KEY, qModel);
    }
  }

  const storedProvider = store?.getItem(PROVIDER_KEY)?.trim().toLowerCase();
  const provider =
    storedProvider === 'anthropic' || storedProvider === 'google' ? storedProvider : undefined;
  const model = store?.getItem(MODEL_KEY)?.trim() || undefined;

  if (model && !provider) {
    return { provider: inferProviderFromModel(model), model };
  }
  return {
    ...(provider ? { provider } : {}),
    ...(model ? { model } : {}),
  };
}
