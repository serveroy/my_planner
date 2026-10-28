import type { AnswerFormat, AvailableTime, CheckinSettings, UpdateMode } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { Card, Chips, Field, SectionTitle, SwitchRow } from '@/ui';

export const defaultAvailableTime: AvailableTime = {
  minutes_per_day: 30,
  days_per_week: 4,
  preferred_days: [],
  preferred_time_of_day: 'any',
  notes: '',
};

export const defaultAnswerFormat: AnswerFormat = {
  language: 'auto',
  verbosity: 'balanced',
  tone: 'warm',
  style: 'mixed',
  use_emojis: false,
  notes: '',
};

export const defaultCheckins: CheckinSettings = {
  enabled: true,
  daily_time: '20:00',
  max_per_day: 2,
  quiet_start: '22:30',
  quiet_end: '08:00',
  inactivity_days: 3,
};

export function AvailableTimeFields({ value, onChange }: { value: AvailableTime; onChange: (v: AvailableTime) => void }) {
  const { t } = useI18n();
  return (
    <>
      <SectionTitle>{t('timeSection')}</SectionTitle>
      <Card>
        <Chips
          label={t('minutesPerDay')}
          options={[15, 20, 30, 45, 60, 90, 120].map((n) => ({ value: n, label: String(n) }))}
          value={value.minutes_per_day}
          onChange={(n) => onChange({ ...value, minutes_per_day: n })}
        />
        <Chips
          label={t('daysPerWeek')}
          options={[1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: n, label: String(n) }))}
          value={value.days_per_week}
          onChange={(n) => onChange({ ...value, days_per_week: n })}
        />
        <Chips
          label={t('timeOfDay')}
          options={(['any', 'morning', 'afternoon', 'evening'] as const).map((v) => ({ value: v, label: t(`tod_${v}`) }))}
          value={value.preferred_time_of_day}
          onChange={(v) => onChange({ ...value, preferred_time_of_day: v })}
        />
      </Card>
    </>
  );
}

export function AnswerFormatFields({ value, onChange }: { value: AnswerFormat; onChange: (v: AnswerFormat) => void }) {
  const { t } = useI18n();
  return (
    <>
      <SectionTitle>{t('formatSection')}</SectionTitle>
      <Card>
        <Chips
          label={t('answerLanguage')}
          options={(['auto', 'he', 'en'] as const).map((v) => ({ value: v, label: t(`lang_${v}`) }))}
          value={value.language}
          onChange={(v) => onChange({ ...value, language: v })}
        />
        <Chips
          label={t('verbosity')}
          options={(['concise', 'balanced', 'detailed'] as const).map((v) => ({ value: v, label: t(`verbosity_${v}`) }))}
          value={value.verbosity}
          onChange={(v) => onChange({ ...value, verbosity: v })}
        />
        <Chips
          label={t('tone')}
          options={(['warm', 'direct', 'motivational'] as const).map((v) => ({ value: v, label: t(`tone_${v}`) }))}
          value={value.tone}
          onChange={(v) => onChange({ ...value, tone: v })}
        />
        <Chips
          label={t('layout')}
          options={(['mixed', 'bullets', 'paragraphs'] as const).map((v) => ({ value: v, label: t(`style_${v}`) }))}
          value={value.style}
          onChange={(v) => onChange({ ...value, style: v })}
        />
        <SwitchRow label={t('emojis')} value={value.use_emojis} onChange={(v) => onChange({ ...value, use_emojis: v })} />
        <Field label={t('formatNotes')} value={value.notes} onChangeText={(notes) => onChange({ ...value, notes })} />
      </Card>
    </>
  );
}

export function UpdateModeField({ value, onChange }: { value: UpdateMode; onChange: (v: UpdateMode) => void }) {
  const { t } = useI18n();
  return (
    <>
      <SectionTitle>{t('updatesSection')}</SectionTitle>
      <Card>
        <Chips
          label={t('updateMode')}
          options={(['ask', 'auto'] as const).map((v) => ({ value: v, label: t(`mode_${v}`) }))}
          value={value}
          onChange={onChange}
        />
      </Card>
    </>
  );
}

export function CheckinFields({ value, onChange }: { value: CheckinSettings; onChange: (v: CheckinSettings) => void }) {
  const { t } = useI18n();
  return (
    <>
      <SectionTitle>{t('checkinsSection')}</SectionTitle>
      <Card>
        <SwitchRow label={t('checkinsEnabled')} value={value.enabled} onChange={(enabled) => onChange({ ...value, enabled })} />
        {value.enabled ? (
          <Field
            label={t('dailyTime')}
            value={value.daily_time}
            onChangeText={(daily_time) => onChange({ ...value, daily_time })}
            maxLength={5}
            keyboardType="numbers-and-punctuation"
          />
        ) : null}
      </Card>
    </>
  );
}

export const isHHMM = (v: string) => /^([01]\d|2[0-3]):[0-5]\d$/.test(v);
