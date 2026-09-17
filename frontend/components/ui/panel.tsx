import { cn } from "@/lib/utils";

/** The one card treatment used everywhere — a surface, a hairline border, a small radius.
 * Deliberately not a soft drop-shadow "SaaS card": separation comes from the border + the
 * surface/canvas contrast, matching the instrument-panel language of the rest of the app. */
export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-line bg-surface", className)} {...props} />;
}

export function PanelHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 border-b border-line px-4 py-2.5",
        className,
      )}
      {...props}
    />
  );
}

export function PanelTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn("font-display text-sm font-medium tracking-tight text-ink", className)}
      {...props}
    />
  );
}
