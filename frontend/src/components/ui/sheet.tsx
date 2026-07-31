import * as React from "react"
import { XIcon } from "lucide-react"
import { Dialog as SheetPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Sheet({ ...props }: React.ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />
}

function SheetTrigger({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Trigger>) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

function SheetClose({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Close>) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />
}

function SheetPortal({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Portal>) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />
}

function SheetOverlay({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
  return (
    <SheetPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-black/32 backdrop-blur-[6px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
        className
      )}
      {...props}
    />
  )
}

function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: "top" | "right" | "bottom" | "left"
  showCloseButton?: boolean
}) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "fixed z-50 flex flex-col gap-4 border-border bg-popover text-popover-foreground shadow-[var(--shadow-lg)] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 duration-300",
          side === "right" &&
            "inset-y-[18px] right-[18px] h-[calc(100%-36px)] w-[min(520px,calc(100vw-36px))] rounded-[28px] border data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
          side === "left" &&
            "inset-y-[18px] left-[18px] h-[calc(100%-36px)] w-[min(520px,calc(100vw-36px))] rounded-[28px] border data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left",
          side === "top" &&
            "inset-x-[18px] top-[18px] h-auto rounded-[24px] border data-[state=open]:slide-in-from-top data-[state=closed]:slide-out-to-top",
          side === "bottom" &&
            "inset-x-[18px] bottom-[18px] h-auto rounded-[24px] border data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close className="absolute top-4 right-4 inline-flex size-9 items-center justify-center rounded-[12px] border border-border bg-[var(--chip-bg-strong)] text-muted-foreground transition-colors hover:text-foreground focus:outline-hidden focus:ring-2 focus:ring-ring disabled:pointer-events-none">
            <XIcon className="size-[var(--icon-sm)]" />
            <span className="sr-only">Close</span>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Content>
    </SheetPortal>
  )
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-[var(--title-description-gap)] px-[18px] py-[14px]", className)}
      {...props}
    />
  )
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn("mt-auto flex flex-col gap-2 px-[18px] py-[14px]", className)}
      {...props}
    />
  )
}

function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("font-semibold text-subheading text-foreground", className)}
      {...props}
    />
  )
}

function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Description>) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-ui text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
}
