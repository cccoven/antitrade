import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { authGoogleConfig } from "@/api/client";

const GOOGLE_SCRIPT_ID = "google-identity-services";
const GOOGLE_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

interface GoogleCredentialResponse {
  credential?: string;
}

interface GoogleAccounts {
  id: {
    initialize: (options: {
      client_id: string;
      callback: (response: GoogleCredentialResponse) => void;
    }) => void;
    renderButton: (
      parent: HTMLElement,
      options: {
        type: "standard";
        theme: "outline";
        size: "large";
        text: "continue_with";
        shape: "rectangular";
        width: number;
      },
    ) => void;
  };
}

declare global {
  interface Window {
    google?: { accounts: GoogleAccounts };
  }
}

function loadGoogleIdentityServices(): Promise<void> {
  if (window.google?.accounts.id) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const existing = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    const handleLoad = () => resolve();
    const handleError = () => reject(new Error("Google Identity Services failed to load"));

    script.addEventListener("load", handleLoad, { once: true });
    script.addEventListener("error", handleError, { once: true });
    if (!existing) {
      script.id = GOOGLE_SCRIPT_ID;
      script.src = GOOGLE_SCRIPT_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  });
}

interface GoogleSignInButtonProps {
  disabled: boolean;
  onCredential: (credential: string) => void;
}

export default function GoogleSignInButton({
  disabled,
  onCredential,
}: GoogleSignInButtonProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const disabledRef = useRef(disabled);
  const onCredentialRef = useRef(onCredential);
  const [clientId, setClientId] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    disabledRef.current = disabled;
    onCredentialRef.current = onCredential;
  }, [disabled, onCredential]);

  useEffect(() => {
    let cancelled = false;
    authGoogleConfig()
      .then((config) => {
        if (!cancelled && config.enabled && config.client_id) {
          setClientId(config.client_id);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!clientId || !containerRef.current) return;
    let cancelled = false;
    const container = containerRef.current;

    loadGoogleIdentityServices()
      .then(() => {
        if (cancelled || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (!disabledRef.current && response.credential) {
              onCredentialRef.current(response.credential);
            }
          },
        });
        container.replaceChildren();
        window.google.accounts.id.renderButton(container, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          width: 368,
        });
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });

    return () => {
      cancelled = true;
      container.replaceChildren();
    };
  }, [clientId]);

  if (loadFailed) {
    return (
      <div className="text-center text-caption text-muted-foreground">
        {t("auth.googleUnavailable")}
      </div>
    );
  }
  if (!clientId) return null;

  return (
    <div
      className={disabled ? "pointer-events-none opacity-60" : undefined}
      aria-disabled={disabled}
    >
      <div ref={containerRef} className="flex min-h-10 justify-center" />
      <div className="my-1 flex items-center gap-3 text-caption text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        <span>{t("auth.orContinueWith")}</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}
