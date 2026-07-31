import { createContext, useContext, useMemo, type ReactNode } from "react";
import { toast } from "sonner";

import { Toaster } from "@/components/ui/sonner";

type ToastVariant = "error" | "success";

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void;
}

function pushToast(message: string, variant: ToastVariant = "error") {
  if (variant === "success") {
    toast.success(message);
  } else {
    toast.error(message);
  }
}

const ToastContext = createContext<ToastContextValue>({ showToast: pushToast });

/** Call from outside the React tree (e.g. api/client.ts). */
export function showToast(message: string, variant?: ToastVariant) {
  pushToast(message, variant);
}

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const value = useMemo<ToastContextValue>(() => ({ showToast: pushToast }), []);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <Toaster position="bottom-right" closeButton />
    </ToastContext.Provider>
  );
}
