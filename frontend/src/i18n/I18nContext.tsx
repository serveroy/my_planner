import { getLocales } from 'expo-localization';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { I18nManager, Platform } from 'react-native';

import type { Lang } from '@/api/types';
import { getStored, setStored } from '@/lib/storage';

import { type StringKey, strings } from './strings';

interface I18n {
  lang: Lang;
  isRTL: boolean;
  setLang: (lang: Lang) => void;
  t: (key: StringKey, vars?: Record<string, string | number>) => string;
  /** True on native when the layout direction changed and needs an app restart. */
  needsRestart: boolean;
}

const Ctx = createContext<I18n | null>(null);
const STORAGE_KEY = 'ui-language';

function deviceLang(): Lang {
  return getLocales()[0]?.languageCode === 'he' ? 'he' : 'en';
}

function applyDirection(rtl: boolean) {
  if (Platform.OS === 'web') {
    if (typeof document !== 'undefined') {
      document.documentElement.dir = rtl ? 'rtl' : 'ltr';
      document.documentElement.lang = rtl ? 'he' : 'en';
    }
    return;
  }
  // Native layout direction only changes after the app restarts.
  I18nManager.allowRTL(true);
  if (I18nManager.isRTL !== rtl) I18nManager.forceRTL(rtl);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(deviceLang);
  const needsRestart = Platform.OS !== 'web' && I18nManager.isRTL !== (lang === 'he');

  useEffect(() => {
    getStored(STORAGE_KEY).then((v) => {
      if (v === 'he' || v === 'en') setLangState(v);
    });
  }, []);

  useEffect(() => {
    applyDirection(lang === 'he');
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    setStored(STORAGE_KEY, next);
  }, []);

  const t = useCallback(
    (key: StringKey, vars?: Record<string, string | number>) => {
      let s = strings[lang][key] ?? strings.en[key] ?? key;
      for (const [k, v] of Object.entries(vars ?? {})) s = s.replace(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, isRTL: lang === 'he', setLang, t, needsRestart }), [lang, setLang, t, needsRestart]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useI18n outside I18nProvider');
  return ctx;
}
