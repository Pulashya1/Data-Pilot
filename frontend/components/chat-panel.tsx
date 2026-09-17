"use client";

import { useEffect, useState } from "react";
import { ApiError, askQuestion, getMessages } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessageOut } from "@/types";

export function ChatPanel({
  sessionId,
  prefill,
  onPrefillConsumed,
}: {
  sessionId: string;
  prefill?: string | null;
  onPrefillConsumed?: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    <div className="flex flex-col gap-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <h2 className="text-sm font-medium">Ask about your data</h2>
      <div className="flex max-h-96 flex-col gap-2 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-xs text-neutral-500">
            Ask about the dataset, an insight, a decision, or a specific cell (click
            &quot;Ask about this cell&quot; in the notebook below).
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "max-w-[85%] rounded-lg px-3 py-2 text-sm",
              message.role === "user"
                ? "self-end bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                : "self-start bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100",
            )}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
            {message.exploratory_cell_id && (
              <p className="mt-1 text-[10px] uppercase text-neutral-500 dark:text-neutral-400">
                Ran a new exploratory cell to answer this
              </p>
            )}
            {message.degraded && (
              <p className="mt-1 text-[10px] uppercase text-amber-600 dark:text-amber-400">
                Answered without the LLM (unavailable/over budget)
              </p>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
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
          className="flex-1 rounded-md border border-neutral-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-950"
        />
        <button
          type="button"
          onClick={() => void send()}
          disabled={sending || !input.trim()}
          className="rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {sending ? "Asking…" : "Ask"}
        </button>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
