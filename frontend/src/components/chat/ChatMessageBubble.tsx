import { Bot, User } from "lucide-react";
import type { ChatMessage } from "../../types/task";

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

export function ChatMessageBubble({
  message,
}: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex items-start gap-3 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-zinc-900 text-white"
            : "border border-zinc-200 bg-white text-zinc-700"
        }`}
        aria-hidden="true"
      >
        {isUser ? <User size={16} /> : <Bot size={17} />}
      </div>

      <div
        className={`min-w-0 max-w-[85%] rounded-2xl px-4 py-3 sm:max-w-[80%] ${
          isUser
            ? "rounded-tr-sm bg-zinc-900 text-white"
            : "rounded-tl-sm border border-zinc-200 bg-white text-zinc-800"
        }`}
      >
        <p className="whitespace-pre-wrap break-words text-sm leading-6">
          {message.content}
        </p>

        {message.created_at && (
          <time
            className={`mt-2 block text-[11px] ${
              isUser ? "text-zinc-300" : "text-zinc-400"
            }`}
            dateTime={message.created_at}
          >
            {new Intl.DateTimeFormat("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
            }).format(new Date(message.created_at))}
          </time>
        )}
      </div>
    </div>
  );
}