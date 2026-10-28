import { router } from 'expo-router';
import { Pressable } from 'react-native';

import { useMarkRead, useNotifications } from '@/api/hooks';
import { useI18n } from '@/i18n/I18nContext';
import { formatDate, textDir } from '@/lib/text';
import { AppText, Badge, Button, Card, ErrorView, Loading, Row, Screen } from '@/ui';
import { space } from '@/ui/theme';

export default function Notifications() {
  const { t, lang } = useI18n();
  const notifications = useNotifications();
  const markRead = useMarkRead();

  if (notifications.isLoading) return <Loading />;
  if (notifications.error) return <ErrorView error={notifications.error} onRetry={notifications.refetch} />;
  const items = notifications.data ?? [];

  return (
    <Screen>
      {items.some((n) => !n.read_at) ? (
        <Button title={t('markAllRead')} variant="ghost" small onPress={() => markRead.mutate({})} style={{ alignSelf: 'flex-end', marginBottom: space.sm }} />
      ) : null}
      {items.length === 0 ? <AppText muted>{t('noNotifications')}</AppText> : null}
      {items.map((n) => (
        <Pressable
          key={n.id}
          onPress={() => {
            if (!n.read_at) markRead.mutate({ id: n.id });
            if (n.goal_id) router.push(`/goal/${n.goal_id}/chat`);
          }}>
          <Card tone={n.read_at ? undefined : 'primary'}>
            <Row style={{ justifyContent: 'space-between', marginBottom: space.xs }}>
              <AppText weight="700" style={[{ flex: 1 }, textDir(n.title)]}>
                {n.title}
              </AppText>
              {!n.read_at ? <Badge text="•" tone="danger" /> : null}
            </Row>
            <AppText style={textDir(n.body)} numberOfLines={3}>
              {n.body}
            </AppText>
            <AppText muted size={12} style={{ marginTop: space.xs }}>
              {formatDate(n.created_at, lang)}
            </AppText>
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}
