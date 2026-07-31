import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-[10px] border border-transparent text-[length:var(--font-ui)] font-medium transition-[background-color,border-color,color,transform,box-shadow] outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[var(--icon-sm)] focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] focus-visible:ring-offset-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-none hover:brightness-105",
        destructive:
          "border-destructive bg-destructive text-destructive-foreground hover:brightness-105",
        outline:
          "border-[var(--border)] bg-[var(--chip-bg)] text-foreground hover:bg-[var(--nav-item-hover)]",
        secondary:
          "border-border bg-secondary text-secondary-foreground hover:bg-card",
        ghost:
          "text-muted-foreground hover:border-border hover:bg-[var(--accent-ghost)] hover:text-accent-foreground",
        link: "h-auto rounded-none border-0 px-0 py-0 text-accent-foreground underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 has-[>svg]:px-3",
        xs: "h-6 gap-1 rounded-[8px] px-2 has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded-[8px] px-3 has-[>svg]:px-2.5",
        lg: "h-10 px-5 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-7 rounded-[8px] [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
