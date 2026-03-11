"use client";

import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  references?: { id: string; title: string }[];
  onReferenceClick?: (docId: string) => void;
  isStreaming?: boolean;
}

export default function MessageBubble({
  role,
  content,
  references,
  onReferenceClick,
  isStreaming = false,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-indigo-100" : "bg-gray-100",
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-indigo-600" />
        ) : (
          <Bot className="h-4 w-4 text-gray-600" />
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-2.5",
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-white text-gray-800 shadow-sm border border-gray-100",
        )}
      >
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {content}
          {isStreaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-current opacity-70" />
          )}
        </div>

        {/* Document references */}
        {references && references.length > 0 && (
          <div className="mt-2 border-t border-gray-100 pt-2">
            <span className="text-[10px] uppercase text-gray-400">
              Sources:
            </span>
            <div className="mt-1 flex flex-wrap gap-1">
              {references.map((ref) => (
                <button
                  key={ref.id}
                  onClick={() => onReferenceClick?.(ref.id)}
                  className="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] text-indigo-700 hover:bg-indigo-100"
                >
                  {ref.title}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
