"use client";

import { Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { NAV_ITEMS, isActive } from "@/components/layout/nav";
import { SystemStatusPill } from "@/components/layout/system-status-pill";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  // Navigating on mobile should dismiss the drawer.
  React.useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[16rem_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-border bg-surface lg:flex">
        <Brand />
        <NavList pathname={pathname} />
        <div className="border-t border-border p-3">
          <SystemStatusPill />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-surface px-4 py-3 lg:hidden">
          <Brand compact />
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
            className="inline-flex size-9 items-center justify-center rounded-lg border border-border-strong text-muted"
          >
            {mobileOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </header>

        {mobileOpen ? (
          <div className="border-b border-border bg-surface px-3 py-3 lg:hidden">
            <NavList pathname={pathname} />
            <div className="mt-3 border-t border-border pt-3">
              <SystemStatusPill />
            </div>
          </div>
        ) : null}

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}

function Brand({ compact }: { compact?: boolean }) {
  return (
    <Link
      href="/"
      className={cn(
        "flex min-w-0 items-center gap-3",
        compact ? "" : "border-b border-border px-5 py-4",
      )}
      aria-label="Upshot Brand Media — Growth Engine, go to dashboard"
    >
      {/* Swap public/logo.svg for the original brand asset to change this. */}
      <Image
        src="/logo.svg"
        alt="Upshot Brand Media"
        width={320}
        height={96}
        priority
        className={cn("w-auto shrink-0", compact ? "h-9" : "h-11")}
      />
      <span className="min-w-0 border-l border-border pl-3 text-[0.6875rem] font-semibold uppercase leading-[1.35] tracking-[0.08em] text-subtle">
        Growth
        <br />
        Engine
      </span>
    </Link>
  );
}

function NavList({ pathname }: { pathname: string }) {
  return (
    <nav className="flex-1 space-y-0.5 p-3" aria-label="Main">
      {NAV_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent-soft text-accent"
                : "text-muted hover:bg-surface-muted hover:text-foreground",
            )}
          >
            <item.icon className="size-4 shrink-0" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
