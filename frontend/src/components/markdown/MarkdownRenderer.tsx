import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink, Paperclip } from "lucide-react";
import { authedAssetUrl } from "@/api/client";
import ImagePreviewDialog from "@/components/ImagePreviewDialog";
import { cn } from "@/lib/utils";

interface PreviewImage {
  url: string;
  original_name: string | null;
}

export default function MarkdownRenderer({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const [preview, setPreview] = useState<PreviewImage | null>(null);

  if (!text.trim()) return null;

  return (
    <>
      <div className={cn("markdown-document text-ui leading-7 text-foreground", className)}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => <h1 className="mb-4 mt-8 text-heading font-semibold first:mt-0">{children}</h1>,
            h2: ({ children }) => <h2 className="mb-3 mt-7 text-subheading font-semibold first:mt-0">{children}</h2>,
            h3: ({ children }) => <h3 className="mb-2 mt-5 text-ui font-semibold first:mt-0">{children}</h3>,
            p: ({ children }) => <p className="my-3 first:mt-0 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-6">{children}</ul>,
            ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-6">{children}</ol>,
            li: ({ children }) => <li className="pl-1 marker:text-muted-foreground">{children}</li>,
            blockquote: ({ children }) => (
              <blockquote className="my-4 border-l-2 border-primary bg-primary/5 px-4 py-2 text-muted-foreground">
                {children}
              </blockquote>
            ),
            hr: () => <hr className="my-7 border-border" />,
            table: ({ children }) => (
              <div className="my-5 overflow-x-auto rounded-lg border border-border">
                <table className="w-full border-collapse text-left text-caption [&_tbody_tr:last-child_td]:border-b-0">{children}</table>
              </div>
            ),
            th: ({ children }) => <th className="border-b border-border bg-muted/50 px-3 py-2 font-medium">{children}</th>,
            td: ({ children }) => <td className="border-b border-border/70 px-3 py-2">{children}</td>,
            pre: ({ children }) => (
              <pre className="my-4 overflow-x-auto rounded-lg border border-border bg-muted/50 p-4 text-caption leading-6">
                {children}
              </pre>
            ),
            code: ({ className: codeClassName, children }) =>
              codeClassName ? (
                <code className={codeClassName}>{children}</code>
              ) : (
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-caption text-foreground">{children}</code>
              ),
            a: ({ href, children }) => {
              const isUpload = Boolean(href?.startsWith("/api/uploads/"));
              const url = isUpload ? authedAssetUrl(href) : href;
              return (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className={cn(
                    "font-medium text-primary underline decoration-primary/40 underline-offset-4 hover:decoration-primary",
                    isUpload && "my-1 inline-flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 no-underline hover:border-primary/50 hover:bg-primary/5",
                  )}
                >
                  {isUpload ? <Paperclip className="size-[var(--icon-sm)]" /> : null}
                  <span>{children}</span>
                  {isUpload ? null : <ExternalLink className="inline size-[var(--icon-xs)]" />}
                </a>
              );
            },
            img: ({ src, alt }) => {
              const rawUrl = typeof src === "string" ? src : "";
              const url = rawUrl.startsWith("/api/uploads/") ? authedAssetUrl(rawUrl) : rawUrl;
              return (
                <button
                  type="button"
                  className="group my-4 block max-w-full overflow-hidden rounded-xl border border-border bg-muted/30 text-left shadow-sm"
                  onClick={() => setPreview({ url: rawUrl, original_name: alt || null })}
                >
                  <img
                    src={url}
                    alt={alt || ""}
                    loading="lazy"
                    className="max-h-[560px] max-w-full object-contain transition-transform duration-200 group-hover:scale-[1.01]"
                  />
                  {alt ? <span className="block border-t border-border px-3 py-2 text-caption text-muted-foreground">{alt}</span> : null}
                </button>
              );
            },
          }}
        >
          {text}
        </ReactMarkdown>
      </div>
      <ImagePreviewDialog
        image={preview}
        open={preview != null}
        onOpenChange={(open) => !open && setPreview(null)}
      />
    </>
  );
}
