import { router } from 'expo-router';
import { Fragment } from 'react';
import { Pressable, View } from 'react-native';

import { useMarkRead, useNotifications } from '@/api/hooks';
import type { AppNotification } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { formatDate, textDir } from '@/lib/text';
import { AppText, Button, Card, Divider, ErrorView, Icon, type IconName, Loading, Row, Screen } from '@/ui';
import { radius, space, useColors } from '@/ui/theme';

const ICONS: Record<string, IconName> = {
  checkin: 'bell',
  plan_ready: 'flag',
  revision_proposal: 'edit-3',
  revision_applied: 'refresh-cw',
};

function NotificationRow({ n, onPress }: { n: AppNotification; onPress: () => void }) {
  const { lang } = useI18n();
  const c = useColors();
  const unread = !n.read_at;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({ paddingVertical: space.md, opacity: pressed ? 0.6 : 1 })}>
      <Row style={{ alignItems: 'flex-start', gap: space.md }}>
        <View style={{ width: 30, height: 30, borderRadius: radius.pill, backgroundColor: unread ? c.accentSoft : c.fill, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={ICONS[n.type] ?? 'bell'} size={14} color={unread ? c.accent : c.muted} />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Row style={{ justifyContent: 'space-between' }}>
            <AppText weight={unread ? '600' : '400'} size={13} style={[{ flex: 1 }, textDir(n.title)]} numberOfLines={1}>
              {n.title}
            </AppText>
            <AppText size={11} style={{ color: c.faint }}>{formatDate(n.created_at, lang)}</AppText>
          </Row>
          <AppText muted size={13} style={textDir(n.body)} numberOfLines={2}>
            {n.body}
          </AppText>
        </View>
      </Row>
    </Pressable>
  );
}

export default function Notifications() {
  const { t } = useI18n();
  const c = useColors();
  const notifications = useNotifications();
  const markRead = useMarkRead();

  if (notifications.isLoading) return <Loading />;
  if (notifications.error) return <ErrorView error={notifications.error} onRetry={notifications.refetch} />;
  const items = notifications.data ?? [];

  return (
    <Screen>
      {items.length === 0 ? (
        <View style={{ alignItems: 'center', paddingVertical: space.xl * 2, gap: space.sm }}>
          <Icon name="inbox" size={26} color={c.faint} />
          <AppText muted>{t('noNotifications')}</AppText>
        </View>
      ) : (
        <>
          {items.some((n) => !n.read_at) ? (
            <Button title={t('markAllRead')} icon="check" variant="ghost" small onPress={() => markRead.mutate({})} style={{ alignSelf: 'flex-end', marginBottom: space.xs }} />
          ) : null}
          <Card style={{ paddingVertical: 0 }}>
            {items.map((n, i) => (
              <Fragment key={n.id}>
                {i > 0 ? <Divider /> : null}
                <NotificationRow
                  n={n}
                  onPress={() => {
                    if (!n.read_at) markRead.mutate({ id: n.id });
                    if (n.goal_id) router.push(`/goal/${n.goal_id}/chat`);
                  }}
                />
              </Fragment>
            ))}
          </Card>
        </>
      )}
    </Screen>
  );
}
