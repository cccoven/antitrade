import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/auth-context";
import MfaSettingsSection from "@/components/MfaSettingsSection";
import { useToast } from "@/components/Toast";
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

const controlStyle = { fontSize: "var(--font-ui)" };

export default function AccountSettingsSection() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const {
    changePassword,
    deleteAccount,
    user,
    setLoginDialogOpen,
    updateProfile,
  } = useAuth();
  const [nameDraft, setNameDraft] = useState(user?.name ?? "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setNameDraft(user?.name ?? "");
  }, [user?.name]);

  const handleProfileSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user || savingProfile) return;
    const name = nameDraft.trim();
    if (!name || name === user.name) return;
    setSavingProfile(true);
    try {
      await updateProfile(name);
      showToast(t("settings.account.profileUpdated"), "success");
    } catch {
      // API helper already shows the backend's localized error.
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    if (newPassword.length < 6) {
      showToast(t("auth.passwordTooShort"));
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast(t("settings.account.passwordMismatch"));
      return;
    }
    if (user?.has_password && newPassword === currentPassword) {
      showToast(t("settings.account.passwordUnchanged"));
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(user?.has_password ? currentPassword : null, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      showToast(t("settings.account.passwordChanged"), "success");
    } catch {
      // API helper already shows the backend's localized error.
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!deletePassword || deleting) return;
    setDeleting(true);
    try {
      await deleteAccount(deletePassword);
      showToast(t("settings.account.deleted"), "success");
      setDeleteDialogOpen(false);
      navigate("/", { replace: true });
    } catch {
      // API helper already shows the backend's localized error.
    } finally {
      setDeleting(false);
    }
  };

  if (!user) {
    return (
      <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5">
        <div className="text-ui font-medium">{t("settings.account.loginRequired")}</div>
        <Button className="mt-3" size="sm" style={controlStyle} onClick={() => setLoginDialogOpen(true)}>
          {t("auth.login")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <section>
        <h2 className="mb-3 text-ui font-semibold text-foreground">{t("settings.account.profile")}</h2>
        <form
          onSubmit={handleProfileSubmit}
          className="rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5"
        >
          <div className="max-w-[440px]">
            <div className="text-ui font-medium text-foreground">{t("settings.account.username")}</div>
            <div className="mt-1 text-caption text-muted-foreground">{t("settings.account.usernameDescription")}</div>
            <div className="mt-5 flex flex-col gap-1.5">
              <Label htmlFor="account-username" className="text-caption">{t("settings.account.username")}</Label>
              <Input
                id="account-username"
                value={nameDraft}
                onChange={(event) => setNameDraft(event.target.value)}
                autoComplete="nickname"
                style={controlStyle}
                required
              />
            </div>
            <Button
              type="submit"
              size="sm"
              style={controlStyle}
              className="mt-5"
              disabled={savingProfile || !nameDraft.trim() || nameDraft.trim() === user.name}
            >
              {t("settings.account.saveProfile")}
            </Button>
          </div>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-ui font-semibold text-foreground">{t("settings.account.password")}</h2>
        {user.has_password ? <MfaSettingsSection /> : null}
        <form
          onSubmit={handleSubmit}
          className="mt-3 rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5"
        >
          <div className="max-w-[440px]">
            <div className="text-ui font-medium text-foreground">
              {t(user.has_password
                ? "settings.account.changePassword"
                : "settings.account.setPassword")}
            </div>
            <div className="mt-1 text-caption text-muted-foreground">
              {t(user.has_password
                ? "settings.account.passwordDescription"
                : "settings.account.setPasswordDescription")}
            </div>

            <div className="mt-5 flex flex-col gap-4">
              {user.has_password ? (
                <PasswordField
                  id="current-password"
                  label={t("settings.account.currentPassword")}
                  value={currentPassword}
                  onChange={setCurrentPassword}
                  autoComplete="current-password"
                />
              ) : null}
              <PasswordField
                id="new-password"
                label={t("settings.account.newPassword")}
                value={newPassword}
                onChange={setNewPassword}
                autoComplete="new-password"
              />
              <PasswordField
                id="confirm-password"
                label={t("settings.account.confirmPassword")}
                value={confirmPassword}
                onChange={setConfirmPassword}
                autoComplete="new-password"
              />
            </div>

            <Button
              type="submit"
              size="sm"
              style={controlStyle}
              className="mt-5"
              disabled={
                submitting
                || (user.has_password && !currentPassword)
                || !newPassword
                || !confirmPassword
              }
            >
              {t("settings.account.updatePassword")}
            </Button>
          </div>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-ui font-semibold text-destructive">
          {t("settings.account.dangerZone")}
        </h2>
        <div className="rounded-[12px] border border-destructive/40 bg-destructive/5 p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="max-w-[620px]">
              <div className="text-ui font-medium text-foreground">
                {t("settings.account.deleteAccount")}
              </div>
              <div className="mt-1 text-caption text-muted-foreground">
                {t("settings.account.deleteDescription")}
              </div>
            </div>
            <Button
              variant="destructive"
              size="icon-sm"
              style={controlStyle}
              className="shrink-0"
              aria-label={t("settings.account.deleteAccount")}
              title={t("settings.account.deleteAccount")}
              onClick={() => setDeleteDialogOpen(true)}
              disabled={!user.has_password}
            >
              <Trash2 />
            </Button>
          </div>
        </div>
        {!user.has_password ? (
          <div className="mt-2 text-caption text-muted-foreground">
            {t("settings.account.setPasswordBeforeDelete")}
          </div>
        ) : null}
      </section>

      <Dialog
        open={deleteDialogOpen}
        onOpenChange={(open) => {
          if (deleting) return;
          setDeleteDialogOpen(open);
          if (!open) setDeletePassword("");
        }}
      >
        <DialogContent showCloseButton={false} className="sm:max-w-[460px]">
          <form className="grid gap-4" onSubmit={handleDeleteAccount}>
            <DialogHeader>
              <DialogTitle className="text-destructive">
                {t("settings.account.deleteTitle")}
              </DialogTitle>
              <DialogDescription>
                {t("settings.account.deleteDialogDescription", { email: user.email })}
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="delete-account-password" className="text-caption">
                {t("settings.account.deletePasswordLabel")}
              </Label>
              <Input
                id="delete-account-password"
                type="password"
                value={deletePassword}
                onChange={(event) => setDeletePassword(event.target.value)}
                autoComplete="current-password"
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
                disabled={deleting}
                onClick={() => setDeleteDialogOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="submit"
                variant="destructive"
                size="sm"
                style={controlStyle}
                disabled={deleting || !deletePassword}
              >
                {deleting
                  ? t("settings.account.deleting")
                  : t("settings.account.deleteConfirm")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-caption">{label}</Label>
      <Input
        id={id}
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        style={controlStyle}
        required
      />
    </div>
  );
}
