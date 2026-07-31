import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/Toast";
import { useAuth } from "./auth-context";
import GoogleSignInButton from "./GoogleSignInButton";
import type { MfaLoginChallenge } from "@/api/client";

type Mode = "login" | "register";
type Phase = "credentials" | "mfa";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 6;
const controlStyle = { fontSize: "var(--font-ui)", fontWeight: 400 };

export default function AuthDialog() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const {
    loginDialogOpen,
    setLoginDialogOpen,
    login,
    googleLogin,
    register,
    verifyMfaLogin,
  } = useAuth();

  const [mode, setMode] = useState<Mode>("login");
  const [phase, setPhase] = useState<Phase>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState<MfaLoginChallenge | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [useRecoveryCode, setUseRecoveryCode] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loginDialogOpen) {
      // Reset on close
      setEmail("");
      setPassword("");
      setName("");
      setMode("login");
      setPhase("credentials");
      setMfaChallenge(null);
      setMfaCode("");
      setUseRecoveryCode(false);
      setSubmitting(false);
    }
  }, [loginDialogOpen]);

  const handleCredentialsSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting) return;

    if (!EMAIL_REGEX.test(email.trim())) {
      showToast(t("auth.invalidEmail"));
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      showToast(t("auth.passwordTooShort"));
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        const challenge = await login(email.trim(), password);
        if (challenge) {
          setMfaChallenge(challenge);
          setMfaCode("");
          setPassword("");
          setPhase("mfa");
        }
      } else {
        const trimmedName = name.trim();
        await register(
          email.trim(),
          password,
          trimmedName.length > 0 ? trimmedName : undefined,
        );
      }
    } catch {
      // Toast is surfaced via unwrapResponse in the API client
    } finally {
      setSubmitting(false);
    }
  };

  const handleMfaSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting || !mfaChallenge || !mfaCode.trim()) return;
    setSubmitting(true);
    try {
      await verifyMfaLogin(mfaChallenge.token, mfaCode.trim());
    } catch {
      // Toast is surfaced via unwrapResponse in the API client.
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleCredential = async (credential: string) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const challenge = await googleLogin(credential);
      if (challenge) {
        setMfaChallenge(challenge);
        setMfaCode("");
        setPassword("");
        setPhase("mfa");
      }
    } catch {
      // Toast is surfaced via unwrapResponse in the API client.
    } finally {
      setSubmitting(false);
    }
  };

  const returnToCredentials = () => {
    setPhase("credentials");
    setMfaChallenge(null);
    setMfaCode("");
    setUseRecoveryCode(false);
  };

  return (
    <Dialog
      open={loginDialogOpen}
      onOpenChange={(open) => setLoginDialogOpen(open)}
    >
      <DialogContent className="sm:max-w-md" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>
            {phase === "mfa"
              ? t("auth.mfa.title")
              : mode === "login"
                ? t("auth.login")
                : t("auth.register")}
          </DialogTitle>
          {phase === "mfa" ? (
            <DialogDescription>{t("auth.mfa.description")}</DialogDescription>
          ) : null}
        </DialogHeader>
        {phase === "credentials" ? (
          <div className="flex flex-col gap-3">
            <GoogleSignInButton
              disabled={submitting}
              onCredential={handleGoogleCredential}
            />
          <form onSubmit={handleCredentialsSubmit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="auth-email" className="text-ui">{t("auth.email")}</Label>
              <Input
                id="auth-email"
                type="email"
                autoComplete="email"
                className="h-8"
                style={controlStyle}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="auth-password" className="text-ui">{t("auth.password")}</Label>
              <Input
                id="auth-password"
                type="password"
                className="h-8"
                style={controlStyle}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {mode === "register" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="auth-name" className="text-ui">{t("auth.name")}</Label>
                <Input
                  id="auth-name"
                  type="text"
                  autoComplete="nickname"
                  className="h-8 placeholder:text-caption"
                  style={controlStyle}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("auth.namePlaceholder")}
                />
              </div>
            )}
            <button
              type="button"
              className="self-start text-muted-foreground hover:text-foreground"
              style={{ fontSize: "var(--font-caption)" }}
              onClick={() =>
                setMode((prev) => (prev === "login" ? "register" : "login"))
              }
            >
              {mode === "login" ? t("auth.noAccount") : t("auth.hasAccount")}
            </button>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                size="sm"
                style={controlStyle}
                onClick={() => setLoginDialogOpen(false)}
              >
                {t("journal.close")}
              </Button>
              <Button
                type="submit"
                size="sm"
                style={controlStyle}
                disabled={submitting}
              >
                {mode === "login"
                  ? t("auth.loginButton")
                  : t("auth.registerButton")}
              </Button>
            </DialogFooter>
          </form>
          </div>
        ) : (
          <form onSubmit={handleMfaSubmit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="auth-mfa-code" className="text-ui">
                {useRecoveryCode
                  ? t("auth.mfa.recoveryCode")
                  : t("auth.mfa.code")}
              </Label>
              <Input
                id="auth-mfa-code"
                type="text"
                inputMode={useRecoveryCode ? "text" : "numeric"}
                autoComplete={useRecoveryCode ? "off" : "one-time-code"}
                style={controlStyle}
                value={mfaCode}
                onChange={(event) => {
                  const next = useRecoveryCode
                    ? event.target.value.toUpperCase()
                    : event.target.value.replace(/\D/g, "").slice(0, 6);
                  setMfaCode(next);
                }}
                placeholder={useRecoveryCode ? "XXXX-XXXX-XXXX-XXXX" : "000000"}
                autoFocus
                required
              />
            </div>
            <button
              type="button"
              className="self-start text-muted-foreground hover:text-foreground"
              style={{ fontSize: "var(--font-caption)" }}
              onClick={() => {
                setUseRecoveryCode((value) => !value);
                setMfaCode("");
              }}
            >
              {useRecoveryCode
                ? t("auth.mfa.useAuthenticator")
                : t("auth.mfa.useRecovery")}
            </button>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                size="sm"
                style={controlStyle}
                onClick={returnToCredentials}
              >
                {t("auth.mfa.back")}
              </Button>
              <Button
                type="submit"
                size="sm"
                style={controlStyle}
                disabled={submitting || !mfaCode.trim()}
              >
                {t("auth.mfa.verify")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
