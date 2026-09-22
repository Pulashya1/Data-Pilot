"use client";

import { LogOut, RadioTower } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { getCurrentUser, logout } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AuthUser } from "@/types";

/** Gates a page behind the signed-in session cookie (MASTER_PROMPT.md §9, §12 Phase 8),
 * redirecting to `/login` on a 401 instead of letting each page handle that itself. Also the
 * app's top-level chrome — logo, theme toggle, account — shown once authenticated. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      })
      .finally(() => {
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!checked || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas">
        <span className="signal-meter" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </span>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between border-b border-line bg-canvas/90 px-4 backdrop-blur lg:px-8">
        <div className="flex items-center gap-3 sm:gap-6">
          <Link href="/" className="flex items-center gap-2">
            <RadioTower size={17} className="text-accent" />
            <span className="hidden font-display text-[15px] font-semibold tracking-tight text-ink sm:inline">
              DataPilot
            </span>
          </Link>
          <nav aria-label="Main" className="flex items-center gap-1 text-sm">
            {[
              { href: "/", label: "New analysis", active: pathname === "/" },
              {
                href: "/sessions",
                label: "Sessions",
                active: pathname?.startsWith("/sessions") ?? false,
              },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={item.active ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-md px-2.5 py-1 transition-colors",
                  item.active
                    ? "bg-surface-3 text-ink"
                    : "text-ink-tertiary hover:bg-surface-2 hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <div className="h-4 w-px bg-line" aria-hidden="true" />
          <span className="hidden font-mono text-xs text-ink-tertiary sm:inline">{user.email}</span>
          <button
            type="button"
            onClick={() => void logout().then(() => router.replace("/login"))}
            aria-label="Log out"
            title="Log out"
            className="flex h-7 w-7 items-center justify-center rounded-md text-ink-tertiary transition-colors hover:bg-surface-3 hover:text-critical"
          >
            <LogOut size={14} />
          </button>
        </div>
      </header>
      <div className="flex-1">{children}</div>
    </div>
  );
}
