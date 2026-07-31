import { useTranslation } from "react-i18next";
import { LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "./auth-context";

export default function LoginRequiredPage() {
  const { t } = useTranslation();
  const { setLoginDialogOpen } = useAuth();

  return (
    <div className="flex items-center justify-center gap-1 py-24 text-subheading text-muted-foreground">
      <LogIn className="size-5 mr-1" />
      <span>{t("auth.pleaseLogin")}</span>
      <Button
        variant="link"
        className="text-subheading px-0"
        onClick={() => setLoginDialogOpen(true)}
      >
        {t("auth.login")}
      </Button>
      <span>{t("auth.pleaseLoginSuffix")}</span>
    </div>
  );
}
