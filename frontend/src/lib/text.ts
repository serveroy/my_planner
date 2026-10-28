import type { TextStyle } from 'react-native';

const HEBREW = /[֐-׿]/g;
const LATIN = /[A-Za-z]/g;

export function isHebrew(text: string): boolean {
  const he = text.match(HEBREW)?.length ?? 0;
  const en = text.match(LATIN)?.length ?? 0;
  return he > 0 && he >= en * 0.5;
}

/** Direction for a block of user/model text, independent of the UI language. */
export function textDir(text: string): TextStyle {
  const rtl = isHebrew(text);
  return { writingDirection: rtl ? 'rtl' : 'ltr', textAlign: rtl ? 'right' : 'left' };
}

export function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return toISODate(d);
}

export function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  return toISODate(new Date(y, m - 1, d + days));
}

export function formatDate(iso: string, lang: 'en' | 'he'): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(lang === 'he' ? 'he-IL' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function daysUntil(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number);
  const target = new Date(y, m - 1, d).getTime();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((target - today) / 86_400_000);
}

/** ISO timestamp (UTC) of today/tomorrow at a local wall-clock time, for the dev scheduler. */
export function localTimeISO(hh: number, mm: number, offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  d.setHours(hh, mm, 0, 0);
  return d.toISOString();
}
