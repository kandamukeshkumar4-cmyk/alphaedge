"use client";

import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { useMemo, useState } from "react";

import { TerminalSenseChips } from "@/components/terminal/TerminalSenseChips";
import { SENSE_CHIPS, type SenseId } from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

type ChatMessage = ThreadMessageLike & { id: string };

function UserMessage() {
  return (
    <MessagePrimitive.Root className="mb-2 flex justify-end">
      <div className="max-w-[90%] rounded-xl border border-primary/25 bg-primary-dim/50 px-3 py-2 text-sm text-text">
        <MessagePrimitive.Content />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="mb-2 flex justify-start">
      <div className="max-w-[90%] rounded-xl border border-border bg-surface-2/70 px-3 py-2 text-sm text-muted">
        <MessagePrimitive.Content />
      </div>
    </MessagePrimitive.Root>
  );
}

export function TerminalComposer({
  senses,
  onSensesChange,
  onAsk,
  isRunning,
  disabled,
}: {
  senses: SenseId[];
  onSensesChange: (next: SenseId[]) => void;
  onAsk: (question: string, senses: SenseId[]) => Promise<void>;
  isRunning: boolean;
  disabled?: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "sys-hello",
      role: "assistant",
      content:
        "Ask a research question. Steps stream as tables and charts from live paper-market services — simulated funds only, no execution.",
    },
  ]);

  const runtime = useExternalStoreRuntime({
    isRunning,
    isDisabled: disabled || isRunning,
    messages,
    onNew: async (message) => {
      const text = message.content
        .filter((p): p is { type: "text"; text: string } => p.type === "text")
        .map((p) => p.text)
        .join("\n")
        .trim();
      if (!text) return;
      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        content: text,
      };
      const pending: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: "Building research plan and streaming steps…",
      };
      setMessages((prev) => [...prev, userMsg, pending]);
      await onAsk(text, senses);
    },
    convertMessage: (m) => m,
  });

  const senseSet = useMemo(() => new Set(senses), [senses]);

  function toggleSense(id: SenseId) {
    if (senseSet.has(id)) {
      onSensesChange(senses.filter((s) => s !== id));
    } else {
      onSensesChange([...senses, id]);
    }
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div
        data-testid="terminal-composer"
        className="rounded-xl border border-border bg-surface"
      >
        <ThreadPrimitive.Root className="flex flex-col">
          <ThreadPrimitive.Viewport className="max-h-40 overflow-y-auto px-3 pt-3">
            <ThreadPrimitive.Empty>
              <p className="pb-2 text-xs text-muted">Start a research question below.</p>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{ UserMessage, AssistantMessage }}
            />
          </ThreadPrimitive.Viewport>

          <div className="border-t border-border px-3 py-2">
            <p className="mb-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
              Data senses
            </p>
            <TerminalSenseChips
              selected={senseSet}
              onToggle={toggleSense}
              disabled={isRunning}
            />
            {/* Keep chip count stable for smoke even if SenseChips remounts. */}
            <span className="sr-only">{SENSE_CHIPS.length} senses</span>
          </div>

          <ComposerPrimitive.Root className="flex items-end gap-2 border-t border-border p-3">
            <ComposerPrimitive.Input
              rows={2}
              placeholder="e.g. Confluence on nba-2025-01-15-lal-bos…"
              className={cn(
                "min-h-[44px] flex-1 resize-none rounded-lg border border-border bg-bg/55 px-3 py-2 text-sm text-text outline-none placeholder:text-muted-2 focus:border-primary/50",
              )}
            />
            <ComposerPrimitive.Send className="rounded-lg bg-primary px-3 py-2 text-[12px] font-bold text-bg shadow-glow transition hover:brightness-110 disabled:opacity-40">
              Run
            </ComposerPrimitive.Send>
          </ComposerPrimitive.Root>
        </ThreadPrimitive.Root>
        <p className="border-t border-border px-3 py-1.5 font-mono text-[9px] uppercase tracking-wide text-muted-2">
          Analysis only · paper trading · no order submission
        </p>
      </div>
    </AssistantRuntimeProvider>
  );
}
