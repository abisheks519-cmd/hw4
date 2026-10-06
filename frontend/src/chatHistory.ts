import type { Product } from "./api";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  products?: Product[];
  // Heading for a set of matches shown on the page; missing for single-product answers.
  resultsTitle?: string | null;
}

// Saved chats live in the database (signed-in shoppers only); the server sends UTC times
// like "2026-09-28 14:05:00".
export function formatWhen(timestamp: string): string {
  const date = new Date(timestamp.replace(" ", "T") + (timestamp.endsWith("Z") ? "" : "Z"));
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString())
    return `Today, ${date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

// Open the chat assistant from anywhere on the site (e.g. an "Ask our assistant" button).
export const OPEN_CHAT_EVENT = "cc:open-chat";
export const openChat = () => window.dispatchEvent(new Event(OPEN_CHAT_EVENT));
