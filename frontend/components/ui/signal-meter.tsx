import { cn } from "@/lib/utils";

/** The agent's "thinking/streaming" indicator — a four-bar signal/telemetry meter rather than a
 * generic spinner, in keeping with the control-room language (see app/globals.css). */
export function SignalMeter({ className, label }: { className?: string; label?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="signal-meter" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </span>
      {label && <span className="text-xs text-ink-secondary">{label}</span>}
    </span>
  );
}
