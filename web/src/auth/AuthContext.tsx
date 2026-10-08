import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { DEMO, DEV_TOKEN } from '../config';
import { configureAuth } from '../api/client';
import * as cognito from './cognito';
import type { Session } from './cognito';

const DEMO_EMAIL = 'rota@st-aldates.nhs.uk';

interface AuthState {
  /** true once the stored session has been read */
  ready: boolean;
  signedIn: boolean;
  email: string | null;
  signIn: (email: string, password: string) => Promise<cognito.SignInResult>;
  finishNewPassword: (username: string, newPassword: string, challengeSession: string) => Promise<void>;
  enterDemo: () => void;
  signOut: () => void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [session, setSession] = useState<Session | null>(() => (DEMO ? null : cognito.loadSession()));
  const [demoIn, setDemoIn] = useState(() => {
    try {
      return DEMO && sessionStorage.getItem('scrubbed.demo-out') !== '1';
    } catch {
      return DEMO;
    }
  });
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const refreshing = useRef<Promise<Session | null> | null>(null);

  const store = useCallback((s: Session | null) => {
    sessionRef.current = s;
    setSession(s);
    cognito.saveSession(s);
  }, []);

  const signOut = useCallback(() => {
    if (DEMO) {
      try {
        sessionStorage.setItem('scrubbed.demo-out', '1');
      } catch {
        /* ignore */
      }
      setDemoIn(false);
    }
    store(null);
    qc.clear();
  }, [qc, store]);

  useEffect(() => {
    configureAuth(
      async () => {
        if (DEV_TOKEN) return DEV_TOKEN;
        const s = sessionRef.current;
        if (!s) return null;
        if (s.expiresAt - Date.now() > 60_000) return s.idToken;
        if (!refreshing.current) {
          refreshing.current = cognito
            .refresh(s)
            .then((n) => {
              store(n);
              return n;
            })
            .catch(() => {
              store(null);
              return null;
            })
            .finally(() => {
              refreshing.current = null;
            });
        }
        return (await refreshing.current)?.idToken ?? null;
      },
      () => {
        if (!DEV_TOKEN) signOut();
      },
    );
  }, [signOut, store]);

  const value = useMemo<AuthState>(
    () => ({
      ready: true,
      signedIn: DEMO ? demoIn : !!DEV_TOKEN || !!session,
      email: DEMO ? (demoIn ? DEMO_EMAIL : null) : (session?.email ?? null),
      async signIn(email, password) {
        const r = await cognito.signIn(email, password);
        if (r.kind === 'session') store(r.session);
        return r;
      },
      async finishNewPassword(username, newPassword, challengeSession) {
        store(await cognito.completeNewPassword(username, newPassword, challengeSession));
      },
      enterDemo() {
        try {
          sessionStorage.removeItem('scrubbed.demo-out');
        } catch {
          /* ignore */
        }
        setDemoIn(true);
      },
      signOut,
    }),
    [demoIn, session, signOut, store],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside AuthProvider');
  return v;
}
