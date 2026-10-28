import { useState } from 'react';
import { View } from 'react-native';

import { useDecideRevision } from '@/api/hooks';
import type { Revision } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { textDir } from '@/lib/text';
import { AppText, Badge, Button, Card, Icon, Row } from '@/ui';
import { space, useColors } from '@/ui/theme';

export function RevisionCard({ goalId, revision }: { goalId: number; revision: Revision }) {
  const { t } = useI18n();
  const c = useColors();
  const decide = useDecideRevision(goalId);
  const [details, setDetails] = useState(false);
  return (
    <Card tone="warning">
      <Row style={{ marginBottom: 4 }}>
        <Icon name="edit-3" size={15} color={c.warning} />
        <AppText weight="600">{t('pendingTitle')}</AppText>
      </Row>
      <AppText size={13} style={[{ marginBottom: space.sm }, textDir(revision.explanation)]}>{revision.explanation}</AppText>
      {details ? (
        <View style={{ marginBottom: space.sm }}>
          {revision.changes.map((ch, i) => (
            <AppText key={i} muted size={12} style={{ writingDirection: 'ltr', textAlign: 'left' }}>
              • {ch}
            </AppText>
          ))}
        </View>
      ) : null}
      <Row>
        <Button title={t('approve')} icon="check" small loading={decide.isPending} onPress={() => decide.mutate({ revisionId: revision.id, approve: true })} />
        <Button title={t('reject')} small variant="ghost" disabled={decide.isPending} onPress={() => decide.mutate({ revisionId: revision.id, approve: false })} />
        {revision.changes.length ? (
          <Button title={details ? t('showLess') : t('details')} small variant="ghost" onPress={() => setDetails(!details)} style={{ marginStart: 'auto' }} />
        ) : null}
      </Row>
      {decide.error ? <AppText size={12} style={{ color: c.danger, marginTop: space.sm }}>{decide.error.message}</AppText> : null}
    </Card>
  );
}

export function RevisionStatus({ status }: { status: Revision['status'] }) {
  const { t } = useI18n();
  if (status === 'applied') return <Badge text={t('approved')} tone="success" />;
  if (status === 'rejected') return <Badge text={t('rejected')} tone="muted" />;
  if (status === 'pending') return <Badge text={t('pendingUpdate')} tone="warning" />;
  return <Badge text={status} tone="muted" />;
}
