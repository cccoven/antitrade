import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Copy, Download, ShieldCheck } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

import {
  authMfaStatus,
  authRegenerateMfaRecoveryCodes,
  authStartMfaSetup,
  type MfaSetup,
  type MfaStatus,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { useToast } from "@/components/Toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const controlStyle = { fontSize: "var(--font-ui)", fontWeight: 400 };

type DialogMode = "setup" | "disable" | "regenerate" | null;
type DialogStep = "password" | "scan" | "codes";

export default function MfaSettingsSection() {
  const { t, i18n } = useTranslation();
  const { showToast } = useToast();
  const { confirmMfaSetup, disableMfa, user } = useAuth();
  const [status, setStatus] = useState<MfaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [dialogStep, setDialogStep] = useState<DialogStep>("password");
  const [currentPassword, setCurrentPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [codesSaved, setCodesSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setStatus(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    authMfaStatus()
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const resetDialog = () => {
    setDialogMode(null);
    setDialogStep("password");
    setCurrentPassword("");
    setVerificationCode("");
    setSetup(null);
    setRecoveryCodes([]);
    setCodesSaved(false);
    setSubmitting(false);
  };

  const openDialog = (mode: Exclude<DialogMode, null>) => {
    resetDialog();
    setDialogMode(mode);
  };

  const handleStartSetup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!currentPassword || submitting) return;
    setSubmitting(true);
    try {
      const result = await authStartMfaSetup({
        current_password: currentPassword,
      });
      setSetup(result);
      setCurrentPassword("");
      setVerificationCode("");
      setDialogStep("scan");
    } catch {
      // API helper already shows the localized error.
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmSetup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (verificationCode.length !== 6 || submitting) return;
    setSubmitting(true);
    try {
      const codes = await confirmMfaSetup(verificationCode);
      setVerificationCode("");
      setRecoveryCodes(codes);
      setStatus({
        enabled: true,
        enabled_at: new Date().toISOString(),
        recovery_codes_remaining: codes.length,
      });
      setDialogStep("codes");
      showToast(t("settings.account.mfa.enabledToast"), "success");
    } catch {
      // API helper already shows the localized error.
    } finally {
      setSubmitting(false);
    }
  };

  const handleSensitiveAction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!dialogMode || !currentPassword || !verificationCode.trim() || submitting) {
      return;
    }
    setSubmitting(true);
    try {
      if (dialogMode === "disable") {
        await disableMfa(currentPassword, verificationCode.trim());
        setStatus({
          enabled: false,
          enabled_at: null,
          recovery_codes_remaining: 0,
        });
        showToast(t("settings.account.mfa.disabledToast"), "success");
        resetDialog();
      } else if (dialogMode === "regenerate") {
        const codes = await authRegenerateMfaRecoveryCodes({
          current_password: currentPassword,
          code: verificationCode.trim(),
        });
        setCurrentPassword("");
        setVerificationCode("");
        setRecoveryCodes(codes);
        setStatus((previous) => previous ? {
          ...previous,
          recovery_codes_remaining: codes.length,
        } : previous);
        setDialogStep("codes");
        showToast(t("settings.account.mfa.regeneratedToast"), "success");
      }
    } catch {
      // API helper already shows the localized error.
    } finally {
      setSubmitting(false);
    }
  };

  const copyText = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      showToast(t("settings.account.mfa.copied"), "success");
    } catch {
      showToast(t("error.generic"));
    }
  };

  const downloadRecoveryCodes = () => {
    const body = [
      "AntiTrade recovery codes",
      "",
      ...recoveryCodes,
    ].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "antitrade-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  const enabledDate = status?.enabled_at
    ? new Date(status.enabled_at).toLocaleDateString(i18n.resolvedLanguage)
    : null;

  return (
    <>
      <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-[620px]">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-[var(--icon-sm)] text-muted-foreground" />
              <div className="text-ui font-medium text-foreground">
                {t("settings.account.mfa.title")}
              </div>
              {!loading && status ? (
                <Badge variant={status.enabled ? "default" : "outline"}>
                  {status.enabled
                    ? t("settings.account.mfa.on")
                    : t("settings.account.mfa.off")}
                </Badge>
              ) : null}
            </div>
            <div className="mt-1 text-caption text-muted-foreground">
              {t("settings.account.mfa.description")}
            </div>
            {status?.enabled ? (
              <div className="mt-2 text-caption text-muted-foreground">
                {t("settings.account.mfa.enabledMeta", {
                  date: enabledDate,
                  count: status.recovery_codes_remaining,
                })}
              </div>
            ) : null}
          </div>
          {!loading && status ? (
            <div className="flex shrink-0 gap-2">
              {status.enabled ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    style={controlStyle}
                    onClick={() => openDialog("regenerate")}
                  >
                    {t("settings.account.mfa.regenerate")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    style={controlStyle}
                    onClick={() => openDialog("disable")}
                  >
                    {t("settings.account.mfa.disable")}
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  style={controlStyle}
                  onClick={() => openDialog("setup")}
                >
                  {t("settings.account.mfa.enable")}
                </Button>
              )}
            </div>
          ) : null}
        </div>
      </div>

      <Dialog
        open={dialogMode !== null}
        onOpenChange={(open) => {
          if (submitting) return;
          if (!open && dialogStep === "codes" && !codesSaved) return;
          if (!open) resetDialog();
        }}
      >
        <DialogContent showCloseButton={false} className="sm:max-w-[500px]">
          {dialogStep === "password" ? (
            <form className="grid gap-4" onSubmit={
              dialogMode === "setup" ? handleStartSetup : handleSensitiveAction
            }>
              <DialogHeader>
                <DialogTitle>{dialogTitle(dialogMode, t)}</DialogTitle>
                <DialogDescription>
                  {dialogMode === "setup"
                    ? t("settings.account.mfa.setupPasswordDescription")
                    : dialogMode === "disable"
                      ? t("settings.account.mfa.disableDescription")
                      : t("settings.account.mfa.regenerateDescription")}
                </DialogDescription>
              </DialogHeader>
              <PasswordInput
                value={currentPassword}
                onChange={setCurrentPassword}
                label={t("settings.account.currentPassword")}
              />
              {dialogMode !== "setup" ? (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="mfa-sensitive-code" className="text-caption">
                    {t("settings.account.mfa.codeOrRecovery")}
                  </Label>
                  <Input
                    id="mfa-sensitive-code"
                    value={verificationCode}
                    onChange={(event) => setVerificationCode(event.target.value)}
                    autoComplete="one-time-code"
                    style={controlStyle}
                    required
                  />
                </div>
              ) : null}
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  style={controlStyle}
                  onClick={resetDialog}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  type="submit"
                  variant={dialogMode === "disable" ? "destructive" : "default"}
                  size="sm"
                  style={controlStyle}
                  disabled={
                    submitting
                    || !currentPassword
                    || (dialogMode !== "setup" && !verificationCode.trim())
                  }
                >
                  {dialogMode === "disable"
                    ? t("settings.account.mfa.disable")
                    : t("settings.account.mfa.continue")}
                </Button>
              </DialogFooter>
            </form>
          ) : null}

          {dialogStep === "scan" && setup ? (
            <form className="grid gap-4" onSubmit={handleConfirmSetup}>
              <DialogHeader>
                <DialogTitle>{t("settings.account.mfa.scanTitle")}</DialogTitle>
                <DialogDescription>
                  {t("settings.account.mfa.scanDescription")}
                </DialogDescription>
              </DialogHeader>
              <div className="flex justify-center">
                <div className="rounded-[12px] bg-white p-3">
                  <QRCodeSVG value={setup.otpauth_uri} size={176} level="M" />
                </div>
              </div>
              <div className="rounded-[10px] border border-border bg-muted/40 p-3">
                <div className="text-caption text-muted-foreground">
                  {t("settings.account.mfa.manualKey")}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <code className="min-w-0 flex-1 break-all text-caption text-foreground">
                    {setup.manual_key}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    style={controlStyle}
                    aria-label={t("settings.account.mfa.copy")}
                    onClick={() => copyText(setup.manual_key)}
                  >
                    <Copy />
                  </Button>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="mfa-setup-code" className="text-caption">
                  {t("settings.account.mfa.code")}
                </Label>
                <Input
                  id="mfa-setup-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={verificationCode}
                  onChange={(event) => setVerificationCode(
                    event.target.value.replace(/\D/g, "").slice(0, 6),
                  )}
                  placeholder="000000"
                  style={controlStyle}
                  autoFocus
                  required
                />
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  style={controlStyle}
                  onClick={resetDialog}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  style={controlStyle}
                  disabled={submitting || verificationCode.length !== 6}
                >
                  {t("settings.account.mfa.confirm")}
                </Button>
              </DialogFooter>
            </form>
          ) : null}

          {dialogStep === "codes" ? (
            <div className="grid gap-4">
              <DialogHeader>
                <DialogTitle>{t("settings.account.mfa.recoveryTitle")}</DialogTitle>
                <DialogDescription>
                  {t("settings.account.mfa.recoveryDescription")}
                </DialogDescription>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-2 rounded-[12px] border border-border bg-muted/40 p-3">
                {recoveryCodes.map((code) => (
                  <code key={code} className="text-caption text-foreground">
                    {code}
                  </code>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  style={controlStyle}
                  onClick={() => copyText(recoveryCodes.join("\n"))}
                >
                  <Copy data-icon="inline-start" />
                  {t("settings.account.mfa.copyCodes")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  style={controlStyle}
                  onClick={downloadRecoveryCodes}
                >
                  <Download data-icon="inline-start" />
                  {t("settings.account.mfa.downloadCodes")}
                </Button>
              </div>
              <label className="flex items-start gap-2 text-caption text-muted-foreground">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={codesSaved}
                  onChange={(event) => setCodesSaved(event.target.checked)}
                />
                {t("settings.account.mfa.savedAcknowledgement")}
              </label>
              <DialogFooter>
                <Button
                  type="button"
                  size="sm"
                  style={controlStyle}
                  disabled={!codesSaved}
                  onClick={resetDialog}
                >
                  {t("settings.account.mfa.done")}
                </Button>
              </DialogFooter>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function PasswordInput({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="mfa-current-password" className="text-caption">
        {label}
      </Label>
      <Input
        id="mfa-current-password"
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="current-password"
        style={controlStyle}
        autoFocus
        required
      />
    </div>
  );
}

function dialogTitle(
  mode: DialogMode,
  t: (key: string) => string,
) {
  if (mode === "setup") return t("settings.account.mfa.setupTitle");
  if (mode === "disable") return t("settings.account.mfa.disableTitle");
  return t("settings.account.mfa.regenerateTitle");
}
