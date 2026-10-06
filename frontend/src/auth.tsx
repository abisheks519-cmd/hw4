import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, login as apiLogin, logout as apiLogout, signup as apiSignup, type SignupInput, type User } from "./api";

interface AuthValue {
  user: User | null;
  ready: boolean; // false until we've asked the server who is signed in
  login: (email: string, password: string) => Promise<void>;
  signup: (input: SignupInput) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

// Browser storage used by earlier versions (sign-in and guest chats now live on the server).
const OLD_STORAGE_KEYS = ["campus-customs-user"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  // The session is an HttpOnly cookie, so ask the server who is signed in (survives page refreshes).
  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true));
    OLD_STORAGE_KEYS.forEach((k) => localStorage.removeItem(k));
    Object.keys(localStorage)
      .filter((k) => k.startsWith("campus-customs-chats:"))
      .forEach((k) => localStorage.removeItem(k));
  }, []);

  const value: AuthValue = {
    user,
    ready,
    login: async (email, password) => setUser(await apiLogin(email, password)),
    signup: async (input) => setUser(await apiSignup(input)),
    logout: async () => {
      await apiLogout().catch(() => undefined);
      setUser(null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
