import { ArrowUp, LoaderCircle } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent } from "react";

interface ChatComposerProps {
  onSend: (message: string) => Promise<void>;
  sending: boolean;
  disabled?: boolean;
}

const MAX_MESSAGE_LENGTH = 1000;

export function ChatComposer({
  onSend,
  sending,
  disabled = false,
}: ChatComposerProps) {
  const [value, setValue] = useState("");

  const canSend =
    value.trim().length > 0 &&
    value.trim().length <= MAX_MESSAGE_LENGTH &&
    !sending &&
    !disabled;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canSend) {
      return;
    }

    const message = value.trim();
    setValue("");

    try {
      await onSend(message);
    } catch {
      setValue(message);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();

      if (canSend) {
        event.currentTarget.form?.requestSubmit();
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="relative">
      <label htmlFor="chat-message" className="sr-only">
        Message the TaskFlow assistant
      </label>

      <textarea
        id="chat-message"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask TaskFlow to manage your tasks..."
        rows={2}
        maxLength={MAX_MESSAGE_LENGTH}
        disabled={sending || disabled}
        className="block min-h-24 w-full resize-none rounded-xl border border-zinc-200 bg-white px-4 py-4 pr-14 text-sm leading-6 text-zinc-900 outline-none transition-shadow placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-2 focus:ring-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-50"
      />

      <button
        type="submit"
        disabled={!canSend}
        aria-label="Send message"
        className="absolute bottom-[2.75rem] right-3 flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-white shadow-sm transition-colors hover:bg-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400"
      >
        {sending ? (
          <LoaderCircle
            size={17}
            className="animate-spin"
            aria-hidden="true"
          />
        ) : (
          <ArrowUp size={18} aria-hidden="true" />
        )}
      </button>

      <div className="mt-2 flex items-center justify-between gap-3 px-1">
        <p className="text-xs text-zinc-400">
          Enter to send · Shift + Enter for a new line
        </p>

        <p
          className={`shrink-0 text-xs ${
            value.length > MAX_MESSAGE_LENGTH - 100
              ? "text-amber-600"
              : "text-zinc-400"
          }`}
        >
          {value.length}/{MAX_MESSAGE_LENGTH}
        </p>
      </div>
    </form>
  );
}