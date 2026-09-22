"use client";

import {
  ArrowUp,
  FlaskConical,
  MessageCircleQuestion,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { MARKDOWN_COMPONENTS, markdownElement } from "@/components/notebook-panel";
import { SignalMeter } from "@/components/ui/signal-meter";
import { ApiError, askQuestion, getMessages } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessageOut } from "@/types";

const SUGGESTIONS = [
  "What are the biggest data quality problems here?",
  "Which columns look most related to the target?",
  "What should I fix before training a model?",
  "Explain the most recent insight in plain language.",
];

// Chat bubbles inherit their text size and color from the bubble, unlike notebook prose.
const CHAT_P = markdownElement("p", "mb-1.5 whitespace-pre-wrap last:mb-0");
const CHAT_UL = markdownElement("ul", "mb-1.5 list-disc pl-4 last:mb-0");
const CHAT_OL = markdownElement("ol", "mb-1.5 list-decimal pl-4 last:mb-0");

const CELL_REFERENCE = /@cell-(\d+)/g;
const CELL_HREF_PREFIX = "#cell-";

/** Turns `@cell-3` mentions into markdown links the renderer below makes clickable. */
function linkCellReferences(content: string): string {
  return content.replace(CELL_REFERENCE, (match, position: string) => {
    return `[${match}](${CELL_HREF_PREFIX}${position})`;
  });
}

function MessageBody({
  content,
  onCellLinkClick,
}: {
  content: string;
  onCellLinkClick?: (position: number) => void;
}) {
  return (
    <ReactMarkdown
      components={{
        ...MARKDOWN_COMPONENTS,
        p: CHAT_P,
        ul: CHAT_UL,
        ol: CHAT_OL,
        a: ({ href, children }) => {
          if (href?.startsWith(CELL_HREF_PREFIX)) {
            const position = Number(href.slice(CELL_HREF_PREFIX.length));
            return (
              <button
                type="button"
                onClick={() => onCellLinkClick?.(position)}
                className="rounded bg-accent/15 px-1 font-mono text-[0.85em] text-accent-strong hover:bg-accent/25"
              >
                {children}
              </button>
            );
          }
          return (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline underline-offset-2"
            >
              {children}
            </a>
          );
        },
      }}
    >
      {linkCellReferences(content)}
    </ReactMarkdown>
  );
}

export function ChatPanel({
  sessionId,
  prefill,
  onPrefillConsumed,
  onCellLinkClick,
  className,
}: {
  sessionId: string;
  prefill?: string | null;
  onPrefillConsumed?: () => void;
  /** Called when the user clicks an `@cell-N` reference in a message. */
  onCellLinkClick?: (position: number) => void;
  className?: string;
}) {
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [input, setInput] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sending = pendingQuestion !== null;

  useEffect(() => {
    getMessages(sessionId)
      .then(setMessages)
      .catch(() => undefined);
  }, [sessionId]);

  useEffect(() => {
    if (!prefill) return;
    setInput((prev) => (prev ? `${prev} ${prefill} ` : `${prefill} `));
    onPrefillConsumed?.();
    inputRef.current?.focus();
  }, [prefill, onPrefillConsumed]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, pendingQuestion]);

  // Grow the textarea with its content, up to about five lines.
  useEffect(() => {
    const node = inputRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight + 2, 120)}px`;
    node.style.overflowY = node.scrollHeight > 118 ? "auto" : "hidden";
  }, [input]);

  const send = async (text: string = input) => {
    const content = text.trim();
    if (!content || sending) return;
    setPendingQuestion(content);
    setError(null);
    setInput("");
    try {
      await askQuestion(sessionId, content);
      setMessages(await getMessages(sessionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send your question.");
      // Give the question back so it doesn't have to be retyped.
      setInput(content);
    } finally {
      setPendingQuestion(null);
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
        aria-live="polite"
      >
        {messages.length === 0 && !sending && (
          <div className="flex flex-1 flex-col justify-center gap-4 py-6">
            <div className="flex flex-col items-center gap-2 text-center">
              <MessageCircleQuestion size={22} className="text-ink-tertiary" />
              <p className="max-w-[240px] text-xs leading-relaxed text-ink-tertiary">
                Ask about the dataset, an insight, a decision, or a specific cell. Type @cell-3 to
                point at cell 3.
              </p>
            </div>
            <ul className="flex flex-col gap-1.5">
              {SUGGESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    onClick={() => void send(suggestion)}
                    className="w-full rounded-md border border-line px-3 py-2 text-left text-xs text-ink-secondary transition-colors hover:border-line-strong hover:bg-surface-2 hover:text-ink"
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "animate-fade-in max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed",
              message.role === "user"
                ? "self-end bg-accent/15 text-ink"
                : "self-start border border-line bg-surface-2 text-ink",
            )}
          >
            <MessageBody content={message.content} onCellLinkClick={onCellLinkClick} />
            {message.exploratory_cell_id && (
              <p className="mt-2 flex items-center gap-1 border-t border-line-strong/50 pt-1.5 text-[11px] text-ink-tertiary">
                <FlaskConical size={11} />
                Ran a new exploratory cell to answer this. It&apos;s in the notebook.
              </p>
            )}
            {message.degraded && (
              <p className="mt-2 flex items-center gap-1 text-[11px] text-warning">
                <TriangleAlert size={11} />
                Answered without the LLM (unavailable or over budget), so this is a basic answer.
              </p>
            )}
          </div>
        ))}
        {pendingQuestion && (
          <>
            <div className="animate-fade-in max-w-[90%] self-end rounded-lg bg-accent/15 px-3 py-2 text-sm leading-relaxed text-ink">
              <p className="whitespace-pre-wrap">{pendingQuestion}</p>
            </div>
            <div className="animate-fade-in flex max-w-[90%] items-center gap-2 self-start rounded-lg border border-line bg-surface-2 px-3 py-2.5">
              <SignalMeter label="Thinking" />
            </div>
          </>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
        className="flex items-end gap-2 border-t border-line p-3"
      >
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Ask a question…"
          aria-label="Your question"
          disabled={sending}
          className="styled-scrollbar max-h-[120px] flex-1 resize-none rounded-md border border-line-strong bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-ink-tertiary transition-colors focus:border-accent disabled:opacity-50"
        />
        <button
          type="submit"
          aria-label="Ask"
          disabled={sending || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-40"
        >
          <ArrowUp size={16} />
        </button>
      </form>
      {error && <p className="px-4 pb-3 text-xs text-critical">{error}</p>}
      <p className="sr-only">Press Enter to send, Shift+Enter for a new line.</p>
    </div>
  );
}
