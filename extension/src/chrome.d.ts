declare const chrome: {
  runtime: {
    sendMessage: (
      message: unknown,
      callback?: (response: { ok: boolean; error?: string; data?: unknown }) => void,
    ) => void;
    onMessage: {
      addListener: (
        callback: (
          message: unknown,
          sender: unknown,
          sendResponse: (response: { ok: boolean; error?: string; data?: unknown }) => void,
        ) => true | void,
      ) => void;
    };
    lastError?: { message?: string };
  };
  storage: {
    local: {
      get: (
        keys: string[] | Record<string, unknown>,
        callback: (items: Record<string, unknown>) => void,
      ) => void;
      set: (items: Record<string, unknown>, callback?: () => void) => void;
    };
  };
  action?: {
    setBadgeText: (details: { text: string }) => void;
    setBadgeBackgroundColor?: (details: { color: string }) => void;
  };
};
