import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none tracking-wide",
  {
    variants: {
      tone: {
        neutral: "bg-surface-3 text-ink-secondary",
        accent: "bg-accent/12 text-accent-strong",
        secondary: "bg-secondary/12 text-secondary-strong",
        info: "bg-info/12 text-info",
        warning: "bg-warning/12 text-warning",
        critical: "bg-critical/12 text-critical",
        success: "bg-success/12 text-success",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
