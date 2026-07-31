import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-[10px] border border-input bg-[var(--input-bg)] px-3 py-2 text-[length:var(--font-ui)] text-foreground transition-[border-color,box-shadow] outline-none placeholder:text-[var(--text-faint)] focus-visible:border-[var(--accent-strong)] focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
