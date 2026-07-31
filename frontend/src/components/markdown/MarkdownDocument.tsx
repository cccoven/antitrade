import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export default function MarkdownDocument({
  title,
  fallbackTitle,
  tags = [],
  eyebrow,
  children,
  className,
}: {
  title: string;
  fallbackTitle: string;
  tags?: string[];
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article
      className={cn(
        "mx-auto w-full max-w-[880px] overflow-hidden rounded-xl border border-border bg-card/40 shadow-sm",
        className,
      )}
    >
      <header className="border-b border-border bg-muted/20 px-6 py-5 md:px-8">
        {eyebrow ? <div className="mb-1 text-caption text-muted-foreground">{eyebrow}</div> : null}
        <h1 className="text-heading font-semibold tracking-tight text-foreground">
          {title || fallbackTitle}
        </h1>
        {tags.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span key={tag} className="rounded-md bg-muted px-2 py-1 text-caption text-muted-foreground">
                {tag}
              </span>
            ))}
          </div>
        ) : null}
      </header>
      <div className="px-6 py-6 md:px-8 md:py-7">{children}</div>
    </article>
  );
}
