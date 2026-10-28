import { router, Stack } from 'expo-router';
import { Pressable, View } from 'react-native';

import { useGoals, useNotifications } from '@/api/hooks';
import type { Goal } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { goalHref } from '@/lib/nav';
import { daysUntil, formatDate, textDir } from '@/lib/text';
import { AppText, Badge, Button, Card, ErrorView, Loading, Row, Screen } from '@/ui';
import { space, useColors } from '@/ui/theme';

function HeaderButtons() {
  const { data } = useNotifications();
  const c = useColors();
  const unread = data?.filter((n) => !n.read_at).length ?? 0;
  return (
    <Row style={{ gap: space.md, paddingHorizontal: space.sm }}>
      <Pressable onPress={() => router.push('/notifications')} accessibilityLabel="notifications">
        <AppText size={20}>🔔{unread ? <AppText size={12} style={{ color: c.danger }} weight="700">{` ${unread}`}</AppText> : null}</AppText>
      </Pressable>
      <Pressable onPress={() => router.push('/settings')} accessibilityLabel="settings">
        <AppText size={20}>⚙️</AppText>
      </Pressable>
    </Row>
  );
}

function GoalCard({ goal }: { goal: Goal }) {
  const { t, lang } = useI18n();
  const left = daysUntil(goal.deadline);
  const tone = goal.status === 'active' ? 'success' : goal.status === 'intake' || goal.status === 'planning' ? 'primary' : 'muted';
  return (
    <Pressable onPress={() => router.push(goalHref(goal))}>
      <Card>
        <Row style={{ justifyContent: 'space-between', marginBottom: space.sm }}>
          <Badge text={t(`status_${goal.status}`)} tone={tone} />
          {goal.unread_notifications ? <Badge text={`${goal.unread_notifications}`} tone="danger" /> : null}
        </Row>
        <AppText size={18} weight="700" style={textDir(goal.title)}>
          {goal.title}
        </AppText>
        <AppText muted style={{ marginTop: 4 }}>
          {formatDate(goal.deadline, lang)} · {t('daysLeft', { n: Math.max(left, 0) })}
        </AppText>
        {goal.has_pending_revision ? (
          <View style={{ marginTop: space.sm }}>
            <Badge text={t('pendingUpdate')} tone="warning" />
          </View>
        ) : null}
      </Card>
    </Pressable>
  );
}

export default function Home() {
  const { t } = useI18n();
  const goals = useGoals();
  return (
    <Screen>
      <Stack.Screen options={{ headerRight: () => <HeaderButtons /> }} />
      {goals.isLoading ? (
        <Loading />
      ) : goals.error ? (
        <ErrorView error={goals.error} onRetry={goals.refetch} />
      ) : (
        <>
          {goals.data?.length === 0 ? (
            <Card tone="primary">
              <AppText>{t('noGoals')}</AppText>
            </Card>
          ) : null}
          {goals.data?.map((g) => <GoalCard key={g.id} goal={g} />)}
          <Button title={`+ ${t('newGoal')}`} onPress={() => router.push('/goals/new')} style={{ marginTop: space.sm }} />
        </>
      )}
    </Screen>
  );
}
