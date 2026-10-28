import { useQueryClient } from '@tanstack/react-query';
import { getCalendars } from 'expo-localization';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api, setToken, setUnauthorizedHandler } from '@/api/client';
import type { Lang, TokenOut, User } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { registerForPush } from '@/lib/push';
import { getStored, setStored } from '@/lib/storage';

interface Auth {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string, language: Lang) => Promise<void>;
  logout: () => void;
  setUser: (u: User) => void;
}

const Ctx = createContext<Auth | null>(null);
const TOKEN_KEY = 'auth-token';

export function deviceTimezone(): string {
  return getCalendars()[0]?.timeZone ?? 'Asia/Jerusalem';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();
  const { setLang } = useI18n();

  const logout = useCallback(() => {
    setToken(null);
    setStored(TOKEN_KEY, null);
    setUser(null);
    qc.clear();
  }, [qc]);

  const accept = useCallback(
    async (out: TokenOut) => {
      setToken(out.access_token);
      await setStored(TOKEN_KEY, out.access_token);
      setUser(out.user);
      setLang(out.user.language);
      registerForPush();
    },
    [setLang],
  );

  useEffect(() => {
    setUnauthorizedHandler(logout);
    getStored(TOKEN_KEY)
      .then(async (stored) => {
        if (!stored) return;
        setToken(stored);
        try {
          const me = await api<User>('/me');
          setUser(me);
          setLang(me.language);
          registerForPush();
        } catch {
          setToken(null);
        }
      })
      .finally(() => setReady(true));
  }, [logout, setLang]);

  const value = useMemo<Auth>(
    () => ({
      user,
      ready,
      logout,
      setUser,
      login: async (email, password) => accept(await api<TokenOut>('/auth/login', { body: { email, password } })),
      register: async (email, password, display_name, language) =>
        accept(
          await api<TokenOut>('/auth/register', {
            body: { email, password, display_name, language, timezone: deviceTimezone() },
          }),
        ),
    }),
    [user, ready, logout, accept],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth outside AuthProvider');
  return ctx;
}
