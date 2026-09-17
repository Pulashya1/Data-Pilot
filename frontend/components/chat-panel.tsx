"use client";

import { ArrowUp, MessageCircleQuestion, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { SignalMeter } from "@/components/ui/signal-meter";
import { ApiError, askQuestion, getMessages } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessageOut } from "@/types";

export function ChatPanel({
  sessionId,
  prefill,
  onPrefillConsumed,
  className,
}: {
  sessionId: string;
  prefill?: string | null;
  onPrefillConsumed?: () => void;
  className?: string;
}) {
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getMessages(sessionId)
      .then(setMessages)
      .catch(() => undefined);
  }, [sessionId]);

  useEffect(() => {
    if (!prefill) return;
    setInput((prev) => (prev ? `${prev} ${prefill} ` : `${prefill} `));
    onPrefillConsumed?.();
  }, [prefill, onPrefillConsumed]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, sending]);

  const send = async () => {
    const content = input.trim();
    if (!content || sending) return;
    setSending(true);
    setError(null);
    setInput("");
    try {
      await askQuestion(sessionId, content);
      setMessages(await getMessages(sessionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send your question.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-lg border border-line bg-surface shadow-floating",
        className,
      )}
    >
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <Sparkles size={14} className="text-accent" />
        <h2 className="font-display text-sm font-medium tracking-tight text-ink">
          Ask about your data
        </h2>
      </div>

      <div
        ref={scrollRef}
        className="styled-scrollbar flex flex-1 flex-col gap-2.5 overflow-y-auto px-4 py-3"
      >
        {messages.length === 0 && !sending && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-8 text-center">
            <MessageCircleQuestion size={22} className="text-ink-tertiary" />
            <p className="max-w-[220px] text-xs leading-relaxed text-ink-tertiary">
              Ask about the dataset, an insight, a decision, or a specific cell (click &quot;Ask
              about this cell&quot; in the notebook).
            </p>
          </div>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "animate-fade-in max-w-[88%] rounded-lg px-3 py-2 text-sm leading-relaxed",
              message.role === "user"
                ? "self-end bg-accent/15 text-ink"
                : "self-start border border-line bg-surface-2 text-ink",
            )}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
            {message.exploratory_cell_id && (
              <p className="mt-1.5 border-t border-line-strong/50 pt-1 text-[10px] uppercase tracking-wide text-ink-tertiary">
                Ran a new exploratory cell to answer this
              </p>
            )}
            {message.degraded && (
              <p className="mt-1.5 text-[10px] uppercase tracking-wide text-warning">
                Answered without the LLM (unavailable/over budget)
              </p>
            )}
          </div>
        ))}
        {sending && (
          <div className="animate-fade-in flex max-w-[88%] items-center gap-2 self-start rounded-lg border border-line bg-surface-2 px-3 py-2.5">
            <SignalMeter />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-line p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Ask a question…"
          disabled={sending}
          className="flex-1 rounded-md border border-line-strong bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-ink-tertiary transition-colors focus:border-accent disabled:opacity-50"
        />
        <button
          type="button"
          aria-label="Ask"
          onClick={() => void send()}
          disabled={sending || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-40"
        >
          <ArrowUp size={16} />
        </button>
      </div>
      {error && <p className="px-4 pb-3 text-xs text-critical">{error}</p>}
    </div>
  );
}
