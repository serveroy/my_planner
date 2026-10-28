import { router, Stack } from 'expo-router';
import { Fragment } from 'react';
import { Pressable, View } from 'react-native';

import { useGoals, useNotifications } from '@/api/hooks';
import type { Goal } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { goalHref } from '@/lib/nav';
import { daysUntil, formatDate, textDir } from '@/lib/text';
import { AppText, Badge, Button, Card, Divider, ErrorView, Icon, IconButton, Loading, ProgressBar, Row, Screen } from '@/ui';
import { radius, space, useColors } from '@/ui/theme';

function HeaderButtons() {
  const { t } = useI18n();
  const { data } = useNotifications();
  const unread = data?.some((n) => !n.read_at) ?? false;
  return (
    <Row style={{ gap: 2 }}>
      <IconButton name="bell" label={t('notifications')} badge={unread} onPress={() => router.push('/notifications')} />
      <IconButton name="settings" label={t('settings')} onPress={() => router.push('/settings')} />
    </Row>
  );
}

function elapsed(goal: Goal): number {
  const start = new Date(goal.created_at).getTime();
  const end = new Date(goal.deadline).getTime();
  return end > start ? (Date.now() - start) / (end - start) : 0;
}

function GoalRow({ goal }: { goal: Goal }) {
  const { t, lang, isRTL } = useI18n();
  const c = useColors();
  const left = Math.max(daysUntil(goal.deadline), 0);
  const starting = goal.status === 'intake' || goal.status === 'planning';
  return (
    <Pressable onPress={() => router.push(goalHref(goal))} style={({ pressed }) => ({ paddingVertical: space.md, opacity: pressed ? 0.6 : 1 })}>
      <Row style={{ alignItems: 'flex-start' }}>
        <View style={{ flex: 1, gap: 3 }}>
          <AppText size={15} weight="500" style={textDir(goal.title)} numberOfLines={2}>
            {goal.title}
          </AppText>
          <AppText muted size={12}>
            {formatDate(goal.deadline, lang)} · {t('daysLeft', { n: left })}
          </AppText>
          {starting || goal.status === 'paused' || goal.has_pending_revision ? (
            <Row style={{ gap: 6, marginTop: 2 }}>
              {starting ? <Badge text={t(`status_${goal.status}`)} tone="accent" /> : null}
              {goal.status === 'paused' ? <Badge text={t('status_paused')} tone="muted" /> : null}
              {goal.has_pending_revision ? <Badge text={t('pendingUpdate')} tone="warning" /> : null}
            </Row>
          ) : (
            <View style={{ flexDirection: 'row', marginTop: 4 }}>
              <ProgressBar value={elapsed(goal)} color={c.accent} />
            </View>
          )}
        </View>
        {goal.unread_notifications ? (
          <View style={{ minWidth: 18, height: 18, borderRadius: 9, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 }}>
            <AppText size={11} weight="600" style={{ color: '#fff', lineHeight: 14 }}>{goal.unread_notifications}</AppText>
          </View>
        ) : null}
        <Icon name={isRTL ? 'chevron-left' : 'chevron-right'} size={18} color={c.faint} />
      </Row>
    </Pressable>
  );
}

export default function Home() {
  const { t } = useI18n();
  const c = useColors();
  const goals = useGoals();

  return (
    <Screen>
      <Stack.Screen options={{ headerRight: () => <HeaderButtons /> }} />
      {goals.isLoading ? (
        <Loading />
      ) : goals.error ? (
        <ErrorView error={goals.error} onRetry={goals.refetch} />
      ) : goals.data?.length === 0 ? (
        <Card style={{ alignItems: 'center', paddingVertical: space.xl }}>
          <View style={{ width: 48, height: 48, borderRadius: radius.pill, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="compass" size={24} color={c.accent} />
          </View>
          <AppText size={16} weight="600" style={{ marginTop: space.md }}>{t('emptyTitle')}</AppText>
          <AppText muted size={13} style={{ textAlign: 'center', marginTop: 4, marginBottom: space.lg }}>{t('noGoals')}</AppText>
          <Button title={t('newGoal')} icon="plus" onPress={() => router.push('/goals/new')} />
        </Card>
      ) : (
        <>
          <Card style={{ paddingVertical: 0 }}>
            {goals.data?.map((g, i) => (
              <Fragment key={g.id}>
                {i > 0 ? <Divider /> : null}
                <GoalRow goal={g} />
              </Fragment>
            ))}
          </Card>
          <Button title={t('newGoal')} icon="plus" variant="secondary" onPress={() => router.push('/goals/new')} />
        </>
      )}
    </Screen>
  );
}
