import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-[10px] border border-input bg-[var(--input-bg)] px-3 py-1 text-[length:var(--font-ui)] text-foreground transition-[border-color,background-color,box-shadow] outline-none placeholder:text-[var(--text-faint)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-[length:var(--font-ui)] file:font-medium",
        "focus-visible:border-[var(--accent-strong)] focus-visible:ring-2 focus-visible:ring-ring",
        "aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
