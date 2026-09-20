import { cva } from "class-variance-authority";

/**
 * Kept in its own server-safe module: `button.tsx` is a client component, and
 * a server component (e.g. `not-found.tsx`) cannot call a function exported
 * from a client module.
 */
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent-hover shadow-sm",
        secondary:
          "border border-border-strong bg-surface text-foreground hover:bg-surface-muted",
        ghost: "text-muted hover:bg-surface-muted hover:text-foreground",
        danger: "border border-transparent bg-danger text-white hover:opacity-90",
        dangerGhost:
          "border border-border-strong bg-surface text-danger hover:bg-danger-soft",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-11 px-5 text-base",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);
