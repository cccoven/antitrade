import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  authChangePassword,
  authConfirmMfaSetup,
  authDeleteAccount,
  authDisableMfa,
  authGoogleLogin,
  authLogin,
  authMe,
  authRegister,
  authUpdateProfile,
  authVerifyMfaLogin,
  type AuthResponse,
  type MfaLoginChallenge,
} from "../api/client";
import {
  AUTH_TOKEN_STORAGE_KEY,
  completeAuthentication,
} from "./complete-authentication";
import type { User } from "./auth-types";

const USER_DATA_STORAGE_KEYS = [
  AUTH_TOKEN_STORAGE_KEY,
  "antitrade.assistant.activeId",
  "antitrade.journalState",
  "antitrade.portfolio.activeId",
];
const USER_DATA_STORAGE_PREFIXES = ["dailyReview:draft:"];

function clearLocalUserData() {
  for (const key of USER_DATA_STORAGE_KEYS) {
    window.localStorage.removeItem(key);
  }
  for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
    const key = window.localStorage.key(index);
    if (key && USER_DATA_STORAGE_PREFIXES.some((prefix) => key.startsWith(prefix))) {
      window.localStorage.removeItem(key);
    }
  }
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<MfaLoginChallenge | null>;
  googleLogin: (credential: string) => Promise<MfaLoginChallenge | null>;
  verifyMfaLogin: (challengeToken: string, code: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  deleteAccount: (currentPassword: string) => Promise<void>;
  changePassword: (currentPassword: string | null, newPassword: string) => Promise<void>;
  confirmMfaSetup: (code: string) => Promise<string[]>;
  disableMfa: (currentPassword: string, code: string) => Promise<void>;
  updateProfile: (name: string) => Promise<void>;
  loginDialogOpen: boolean;
  setLoginDialogOpen: (open: boolean) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [loginDialogOpen, setLoginDialogOpen] = useState(false);

  // On mount: read token from localStorage and validate via authMe
  useEffect(() => {
    let cancelled = false;
    const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const me = await authMe();
        if (!cancelled) {
          setUser(me);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Listen for 401 events dispatched by the API interceptor
  useEffect(() => {
    const handler = () => {
      setUser(null);
      setLoginDialogOpen(true);
    };
    window.addEventListener("auth:unauthorized", handler);
    return () => {
      window.removeEventListener("auth:unauthorized", handler);
    };
  }, []);

  const applyAuthResponse = useCallback((res: AuthResponse) => {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, res.token);
    setUser(res.user);
  }, []);

  const finishAuthentication = useCallback((res: AuthResponse) => {
    completeAuthentication(res.token);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authLogin({ email, password });
    if (res.mfa_required) return res.challenge;
    finishAuthentication(res);
    return null;
  }, [finishAuthentication]);

  const googleLogin = useCallback(async (credential: string) => {
    const res = await authGoogleLogin(credential);
    if (res.mfa_required) return res.challenge;
    finishAuthentication(res);
    return null;
  }, [finishAuthentication]);

  const verifyMfaLogin = useCallback(async (challengeToken: string, code: string) => {
    const res = await authVerifyMfaLogin({
      challenge_token: challengeToken,
      code,
    });
    finishAuthentication(res);
  }, [finishAuthentication]);

  const register = useCallback(
    async (email: string, password: string, name?: string) => {
      const res = await authRegister({ email, password, name });
      finishAuthentication(res);
    },
    [finishAuthentication],
  );

  const logout = useCallback(() => {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (name: string) => {
    const updated = await authUpdateProfile({ name });
    setUser(updated);
  }, []);

  const changePassword = useCallback(async (
    currentPassword: string | null,
    newPassword: string,
  ) => {
    const res = await authChangePassword({
      ...(currentPassword ? { current_password: currentPassword } : {}),
      new_password: newPassword,
    });
    applyAuthResponse(res);
  }, [applyAuthResponse]);

  const confirmMfaSetup = useCallback(async (code: string) => {
    const res = await authConfirmMfaSetup({ code });
    applyAuthResponse(res);
    return res.recovery_codes;
  }, [applyAuthResponse]);

  const disableMfa = useCallback(async (
    currentPassword: string,
    code: string,
  ) => {
    const res = await authDisableMfa({
      current_password: currentPassword,
      code,
    });
    applyAuthResponse(res);
  }, [applyAuthResponse]);

  const deleteAccount = useCallback(async (currentPassword: string) => {
    await authDeleteAccount({ current_password: currentPassword });
    clearLocalUserData();
    setUser(null);
    setLoginDialogOpen(false);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        googleLogin,
        verifyMfaLogin,
        register,
        logout,
        deleteAccount,
        changePassword,
        confirmMfaSetup,
        disableMfa,
        updateProfile,
        loginDialogOpen,
        setLoginDialogOpen,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
