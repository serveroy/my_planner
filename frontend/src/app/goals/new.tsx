import { router } from 'expo-router';
import { useState } from 'react';

import { useCreateGoal } from '@/api/hooks';
import type { GoalCreate } from '@/api/types';
import {
  AnswerFormatFields,
  AvailableTimeFields,
  CheckinFields,
  defaultAnswerFormat,
  defaultAvailableTime,
  defaultCheckins,
  isHHMM,
  UpdateModeField,
} from '@/components/GoalFields';
import { useI18n } from '@/i18n/I18nContext';
import { addDays, todayISO } from '@/lib/text';
import { AppText, Button, Card, Chips, Collapsible, Field, Screen, SectionTitle } from '@/ui';
import { space, useColors } from '@/ui/theme';

export default function NewGoal() {
  const { t } = useI18n();
  const c = useColors();
  const create = useCreateGoal();
  const [form, setForm] = useState<GoalCreate>({
    title: '',
    description: '',
    current_state: '',
    deadline: addDays(todayISO(), 90),
    available_time: defaultAvailableTime,
    answer_format: defaultAnswerFormat,
    extra_context: '',
    update_mode: 'ask',
    checkin_settings: defaultCheckins,
  });
  const set = <K extends keyof GoalCreate>(k: K, v: GoalCreate[K]) => setForm((f) => ({ ...f, [k]: v }));

  const validDeadline = /^\d{4}-\d{2}-\d{2}$/.test(form.deadline) && form.deadline > todayISO();
  const valid = form.title.trim().length >= 2 && validDeadline && isHHMM(form.checkin_settings.daily_time);

  const submit = () =>
    create.mutate(form, {
      onSuccess: (goal) => router.replace(`/goal/${goal.id}/intake`),
    });

  return (
    <Screen>
      <SectionTitle>{t('goalSection')}</SectionTitle>
      <Card>
        <Field label={t('goalTitle')} placeholder={t('goalTitlePh')} value={form.title} onChangeText={(v) => set('title', v)} />
        <Field label={t('goalDescription')} value={form.description} onChangeText={(v) => set('description', v)} multiline />
        <Field
          label={t('currentState')}
          placeholder={t('currentStatePh')}
          value={form.current_state}
          onChangeText={(v) => set('current_state', v)}
          multiline
        />
        <Field label={t('deadline')} hint={t('deadlineHint')} value={form.deadline} onChangeText={(v) => set('deadline', v)} maxLength={10} />
        <Chips
          options={[1, 3, 6, 12].map((n) => ({ value: n, label: t('inMonths', { n }) }))}
          value={[] as number[]}
          onChange={(n) => set('deadline', addDays(todayISO(), Math.round(n * 30.4)))}
        />
      </Card>

      <AvailableTimeFields value={form.available_time} onChange={(v) => set('available_time', v)} />

      <Collapsible title={t('preferences')} hint={t('preferencesHint')}>
        <AnswerFormatFields value={form.answer_format} onChange={(v) => set('answer_format', v)} />
        <UpdateModeField value={form.update_mode} onChange={(v) => set('update_mode', v)} />
        <CheckinFields value={form.checkin_settings} onChange={(v) => set('checkin_settings', v)} />
        <Card>
          <Field label={t('extraContext')} value={form.extra_context} onChangeText={(v) => set('extra_context', v)} multiline />
        </Card>
      </Collapsible>

      {create.error ? <AppText size={13} style={{ color: c.danger, marginBottom: space.sm }}>{create.error.message}</AppText> : null}
      <Button title={t('startIntake')} onPress={submit} disabled={!valid} loading={create.isPending} />
    </Screen>
  );
}
