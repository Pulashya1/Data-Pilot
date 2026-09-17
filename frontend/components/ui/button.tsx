import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-fg hover:bg-accent-strong",
        secondary: "bg-surface-3 text-ink hover:bg-line-strong border border-line-strong",
        outline: "border border-line text-ink-secondary hover:border-line-strong hover:text-ink",
        ghost: "text-ink-secondary hover:bg-surface-3 hover:text-ink",
        danger: "bg-critical/10 text-critical hover:bg-critical/20",
      },
      size: {
        sm: "h-7 px-2.5 text-xs",
        md: "h-8 px-3.5 text-sm",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      type={props.type ?? "button"}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
