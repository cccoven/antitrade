export const AUTH_TOKEN_STORAGE_KEY = "antitrade.auth.token";

interface AuthenticationCompletionOptions {
  storage?: Pick<Storage, "setItem">;
  reload?: () => void;
}

export function completeAuthentication(
  token: string,
  options: AuthenticationCompletionOptions = {},
) {
  const storage = options.storage ?? window.localStorage;
  const reload = options.reload ?? (() => window.location.reload());
  storage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  reload();
}
