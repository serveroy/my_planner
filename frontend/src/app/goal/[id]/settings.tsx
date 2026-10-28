import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Platform } from 'react-native';

import { useDeleteGoal, useGoal, useUpdateGoal } from '@/api/hooks';
import type { Goal } from '@/api/types';
import { AnswerFormatFields, AvailableTimeFields, CheckinFields, isHHMM, UpdateModeField } from '@/components/GoalFields';
import { useI18n } from '@/i18n/I18nContext';
import { AppText, Button, ErrorView, Loading, Row, Screen, SectionTitle } from '@/ui';
import { space, useColors } from '@/ui/theme';

type Editable = Pick<Goal, 'available_time' | 'answer_format' | 'update_mode' | 'checkin_settings'>;

export default function GoalSettings() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const goal = useGoal(Number(id));
  if (goal.error) return <ErrorView error={goal.error} onRetry={goal.refetch} />;
  if (!goal.data) return <Loading />;
  return <SettingsForm goal={goal.data} />;
}

function SettingsForm({ goal: g }: { goal: Goal }) {
  const { t } = useI18n();
  const c = useColors();
  const update = useUpdateGoal(g.id);
  const remove = useDeleteGoal(g.id);
  const [form, setForm] = useState<Editable>({
    available_time: g.available_time,
    answer_format: g.answer_format,
    update_mode: g.update_mode,
    checkin_settings: g.checkin_settings,
  });
  const set = <K extends keyof Editable>(k: K, v: Editable[K]) => setForm((f) => ({ ...f, [k]: v }));

  const confirmDelete = () => {
    const doDelete = () => remove.mutate(undefined, { onSuccess: () => router.replace('/') });
    if (Platform.OS === 'web') {
      if (globalThis.confirm?.(t('deleteConfirm'))) doDelete();
    } else {
      Alert.alert(t('deleteGoal'), t('deleteConfirm'), [
        { text: t('cancel'), style: 'cancel' },
        { text: t('deleteGoal'), style: 'destructive', onPress: doDelete },
      ]);
    }
  };

  return (
    <Screen>
      <UpdateModeField value={form.update_mode} onChange={(v) => set('update_mode', v)} />
      <AnswerFormatFields value={form.answer_format} onChange={(v) => set('answer_format', v)} />
      <CheckinFields value={form.checkin_settings} onChange={(v) => set('checkin_settings', v)} />
      <AvailableTimeFields value={form.available_time} onChange={(v) => set('available_time', v)} />
      <Button
        title={update.isSuccess ? t('saved') : t('save')}
        icon={update.isSuccess ? 'check' : undefined}
        onPress={() => update.mutate(form)}
        loading={update.isPending}
        disabled={!isHHMM(form.checkin_settings.daily_time)}
      />
      {update.error ? <AppText size={13} style={{ color: c.danger, marginTop: space.sm }}>{update.error.message}</AppText> : null}

      <SectionTitle>{t('goalStatus')}</SectionTitle>
      <Row style={{ flexWrap: 'wrap' }}>
        {g.current_plan_version ? (
          <>
            {g.status === 'active' ? (
              <Button title={t('pauseGoal')} icon="pause" small variant="secondary" onPress={() => update.mutate({ status: 'paused' })} />
            ) : (
              <Button title={t('resumeGoal')} icon="play" small variant="secondary" onPress={() => update.mutate({ status: 'active' })} />
            )}
            <Button title={t('completeGoal')} icon="award" small variant="secondary" onPress={() => update.mutate({ status: 'completed' })} />
          </>
        ) : null}
        <Button title={t('deleteGoal')} icon="trash-2" small variant="danger" onPress={confirmDelete} loading={remove.isPending} />
      </Row>
    </Screen>
  );
}
