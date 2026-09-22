"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";

export interface TabItem<K extends string> {
  key: K;
  label: string;
  /** A small count or marker shown after the label (e.g. number of notebook cells). */
  count?: number;
  /** Draws attention to a tab whose content needs the user (e.g. a failed cell). */
  alert?: boolean;
}

/** A WAI-ARIA tablist: arrow keys move between tabs, the panel is rendered by the caller with
 * `id={tabPanelId(key)}` and `aria-labelledby={tabId(key)}`. */
export function Tabs<K extends string>({
  items,
  active,
  onChange,
  className,
}: {
  items: TabItem<K>[];
  active: K;
  onChange: (key: K) => void;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const focusTab = (index: number) => {
    const wrapped = (index + items.length) % items.length;
    const item = items[wrapped];
    if (!item) return;
    onChange(item.key);
    refs.current[wrapped]?.focus();
  };

  return (
    <div
      role="tablist"
      className={cn(
        "flex items-end gap-1 overflow-x-auto overflow-y-hidden shadow-[inset_0_-1px_0_rgb(var(--line))]",
        className,
      )}
    >
      {items.map((item, index) => {
        const selected = item.key === active;
        return (
          <button
            key={item.key}
            ref={(node) => {
              refs.current[index] = node;
            }}
            id={tabId(item.key)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={tabPanelId(item.key)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.key)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") focusTab(index + 1);
              if (e.key === "ArrowLeft") focusTab(index - 1);
            }}
            className={cn(
              "relative flex shrink-0 items-center gap-2 border-b-2 px-3 pb-2.5 pt-2 text-sm font-medium transition-colors",
              selected
                ? "border-accent text-ink"
                : "border-transparent text-ink-tertiary hover:text-ink-secondary",
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={cn(
                  "tabular rounded px-1.5 py-0.5 text-[10px] leading-none",
                  selected ? "bg-accent/15 text-accent-strong" : "bg-surface-3 text-ink-tertiary",
                )}
              >
                {item.count}
              </span>
            )}
            {item.alert && (
              <span className="h-1.5 w-1.5 rounded-full bg-critical" aria-label="needs attention" />
            )}
          </button>
        );
      })}
    </div>
  );
}

export function tabId(key: string): string {
  return `tab-${key}`;
}

export function tabPanelId(key: string): string {
  return `tabpanel-${key}`;
}
