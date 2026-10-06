import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useMatch, useNavigate } from "react-router-dom";
import {
  deleteChat,
  formatPrice,
  getChat,
  listChats,
  sendChat,
  type ChatTurn,
  type ConversationSummary,
  type Product,
  type User,
} from "../api";
import { useAssistantResults, useReturnState } from "../assistantResults";
import { useAuth } from "../auth";
import { formatWhen, OPEN_CHAT_EVENT, type ChatMessage } from "../chatHistory";
import { usePageContext } from "../pageContext";

const SUGGESTIONS = ["Show me hoodies", "Anything in gray?", "Hockey gear", "Quarter-zips"];

// Replies may use **bold** (markdown); show it as bold text without inserting any raw HTML.
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))}
    </>
  );
}

const firstName = (user: User) => user.first_name || user.name.split(" ")[0];
const greeting = (user: User | null, returning = false): ChatMessage => ({
  role: "assistant",
  text: returning && user
    ? `Welcome back, ${firstName(user)}! 👋 Here's where we left off.`
    : `Hi${user ? ` ${firstName(user)}` : ""}! I'm the Campus Customs assistant 👋 Ask me about products, colors, sizes, or prices.`,
});

// Remount per signed-in user (or guest) so each account only ever sees its own chats.
export default function ChatWidget() {
  const { user, ready } = useAuth();
  if (!ready) return null; // wait until we know who is signed in
  return <ChatPanel key={user?.id ?? "guest"} user={user} />;
}

function ChatPanel({ user }: { user: User | null }) {
  const signedIn = user !== null;
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"chat" | "history">("chat");
  // Signed-in shoppers' conversations, from the database. Guests have none (nothing is saved).
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([greeting(user)]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const resumed = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { showResults } = useAssistantResults();
  const navigate = useNavigate();
  const onProductPage = useMatch("/products/:productId");
  const returnState = useReturnState();
  const pageContext = usePageContext();

  // "Ask our assistant" buttons elsewhere on the site open the panel.
  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(OPEN_CHAT_EVENT, show);
    return () => window.removeEventListener(OPEN_CHAT_EVENT, show);
  }, []);

  // Opening a product closes the panel so the whole product page is visible; the chat is kept.
  const productPath = onProductPage?.pathname;
  useEffect(() => {
    if (productPath) setOpen(false);
  }, [productPath]);

  // Put a set of matches on the website. A product page doesn't show results, so go to Products.
  const showOnPage = (title: string, products: Product[]) => {
    showResults({ source: "assistant", title, products });
    if (onProductPage) navigate("/products", { state: { keepResults: true } });
  };

  const refreshList = () => {
    if (signedIn) listChats().then(setConversations).catch(() => undefined);
  };
  useEffect(refreshList, []);

  const openConversation = async (id: number, returning = false) => {
    setView("chat");
    setActiveId(id);
    setLoadingChat(true);
    try {
      const saved = await getChat(id);
      setMessages([
        greeting(user, returning),
        ...saved.messages.map((m) => ({ role: m.role, text: m.content, products: m.products, resultsTitle: m.results_title })),
      ]);
    } catch {
      setActiveId(null);
      setMessages([greeting(user), { role: "assistant", text: "Sorry, I couldn't load that chat." }]);
    } finally {
      setLoadingChat(false);
    }
  };

  // Returning shoppers pick up where they left off: the first time the chat opens, show their latest chat.
  useEffect(() => {
    if (open && !resumed.current && conversations.length > 0 && activeId === null && messages.length === 1) {
      resumed.current = true;
      openConversation(conversations[0].id, true);
    }
  }, [open, conversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, view]);

  useEffect(() => {
    if (open && view === "chat") inputRef.current?.focus();
  }, [open, view]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || sending || loadingChat) return;
    setInput("");
    resumed.current = true;
    // Guests send their prior turns; signed-in shoppers' history is read from the database.
    const history: ChatTurn[] = signedIn ? [] : messages.slice(1).map((m) => ({ role: m.role, content: m.text }));
    const withQuestion: ChatMessage[] = [...messages, { role: "user", text: message }];
    setMessages(withQuestion);
    setSending(true);
    let reply: ChatMessage;
    try {
      const res = await sendChat(message, { history, conversationId: activeId, pageContext });
      reply = { role: "assistant", text: res.reply, products: res.products, resultsTitle: res.results_title };
      if (res.conversation_id !== null) {
        setActiveId(res.conversation_id);
        refreshList();
      }
      if (res.results_title && res.products.length > 0) showOnPage(res.results_title, res.products);
    } catch (e) {
      const gone = e instanceof Error && e.message === "Conversation not found";
      if (gone) setActiveId(null);
      reply = {
        role: "assistant",
        text: gone
          ? "That chat was deleted, so I've started a new one. Please ask again."
          : "Sorry, I can't reach the store right now. Please try again.",
      };
    }
    // History and New chat are disabled while a reply is pending, so this chat is still the open one.
    setMessages([...withQuestion, reply]);
    setSending(false);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  // Start fresh; the previous chat stays saved in the history list.
  const newChat = () => {
    resumed.current = true;
    setActiveId(null);
    setMessages([greeting(user)]);
    setInput("");
    setView("chat");
    inputRef.current?.focus();
  };

  const removeConversation = async (id: number) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (id === activeId) {
      setActiveId(null);
      setMessages([greeting(user)]);
    }
    await deleteChat(id).catch(() => undefined);
    refreshList();
  };

  const busy = sending || loadingChat;
  const canReset = (messages.length > 1 || activeId !== null) && !busy;

  return (
    <div className={`chat ${open ? "is-open" : ""}`}>
      {open && (
        <div className="chat-panel" role="dialog" aria-label="Shopping assistant">
          <div className="chat-header">
            <div className="chat-title">
              <strong>Campus Customs</strong>
              <span className="chat-status">
                <i /> Shopping assistant
              </span>
            </div>
            <button
              className={`chat-icon-btn ${view === "history" ? "active" : ""}`}
              onClick={() => setView(view === "history" ? "chat" : "history")}
              disabled={busy}
              title="Previous chats"
              aria-label="Previous chats"
              aria-pressed={view === "history"}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
                <path d="M3 3v5h5" />
                <path d="M12 7v5l3 2" />
              </svg>
            </button>
            <button className="chat-new" onClick={newChat} disabled={!canReset} title="Start a new chat">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
              New chat
            </button>
            <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>

          {view === "history" ? (
            <div className="chat-history">
              <div className="chat-history-head">
                <h4>Previous chats</h4>
                {signedIn && <span>{conversations.length} saved</span>}
              </div>
              {!signedIn ? (
                <div className="chat-history-empty">
                  <div className="chat-history-empty-icon">🔒</div>
                  <p>Save your chats</p>
                  <span>Log in or create an account and your conversations are saved to your account, ready when you come back.</span>
                  <div className="chat-history-auth">
                    <Link to="/login" className="btn btn-primary" onClick={() => setOpen(false)}>
                      Log in
                    </Link>
                    <Link to="/create-account" className="btn btn-outline" onClick={() => setOpen(false)}>
                      Create account
                    </Link>
                  </div>
                </div>
              ) : conversations.length === 0 ? (
                <div className="chat-history-empty">
                  <div className="chat-history-empty-icon">💬</div>
                  <p>No previous chats yet</p>
                  <span>Your conversations are saved to your account so you can pick up where you left off.</span>
                </div>
              ) : (
                <ul className="chat-history-list">
                  {conversations.map((c) => (
                    <li key={c.id} className={c.id === activeId ? "active" : ""}>
                      <button className="chat-history-item" onClick={() => openConversation(c.id)}>
                        <strong>{c.title}</strong>
                        <span>
                          {formatWhen(c.updated_at)} · {c.message_count} message{c.message_count === 1 ? "" : "s"}
                        </span>
                      </button>
                      <button
                        className="chat-history-delete"
                        onClick={() => removeConversation(c.id)}
                        title="Delete chat"
                        aria-label={`Delete chat: ${c.title}`}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <button className="chat-history-new" onClick={newChat}>
                + Start a new chat
              </button>
            </div>
          ) : (
            <>
              <div className="chat-body">
                {messages.map((m, i) => (
                  <div key={i} className={`chat-msg ${m.role}`}>
                    <div className="bubble">
                      <RichText text={m.text} />
                    </div>
                    {m.products && m.products.length > 0 && (
                      <div className="chat-products">
                        {/* A results set previews 3 items here; the full set is shown on the page. */}
                        {(m.resultsTitle ? m.products.slice(0, 3) : m.products).map((p) => (
                          <Link key={p.product_id} to={`/products/${p.product_id}`} state={returnState} className="chat-product">
                            <img src={p.thumb_url} alt="" loading="lazy" decoding="async" />
                            <div>
                              <strong>{p.name}</strong>
                              <span>
                                {formatPrice(p.price)} · {p.total_stock > 0 ? `${p.total_stock} in stock` : "Sold out"}
                              </span>
                            </div>
                          </Link>
                        ))}
                        {m.resultsTitle && (
                          <button className="chat-results-btn" onClick={() => showOnPage(m.resultsTitle!, m.products!)}>
                            View all {m.products.length} on the page →
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {busy && (
                  <div className="chat-msg assistant">
                    <div className="bubble typing">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              {messages.length === 1 && !loadingChat && (
                <div className="chat-suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              )}

              <form className="chat-input" onSubmit={submit}>
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about sizes, colors, prices…"
                />
                <button type="submit" disabled={!input.trim() || busy} aria-label="Send">
                  ➤
                </button>
              </form>
            </>
          )}
        </div>
      )}

      <button className="chat-launcher" aria-label={open ? "Close chat" : "Open chat"} onClick={() => setOpen(!open)}>
        {open ? "×" : "💬"}
        {!open && <span className="chat-launcher-label">Need help?</span>}
      </button>
    </div>
  );
}
