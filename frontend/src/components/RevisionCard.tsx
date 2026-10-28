import { View } from 'react-native';

import { useDecideRevision } from '@/api/hooks';
import type { Revision } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { textDir } from '@/lib/text';
import { AppText, Badge, Button, Card, Row } from '@/ui';
import { space, useColors } from '@/ui/theme';

export function RevisionCard({ goalId, revision }: { goalId: number; revision: Revision }) {
  const { t } = useI18n();
  const c = useColors();
  const decide = useDecideRevision(goalId);
  return (
    <Card tone="warning">
      <AppText weight="700" style={{ marginBottom: space.sm }}>
        {t('pendingTitle')}
      </AppText>
      <AppText style={[{ marginBottom: space.sm }, textDir(revision.explanation)]}>{revision.explanation}</AppText>
      {revision.changes.length ? (
        <View style={{ marginBottom: space.md }}>
          <AppText muted size={12} weight="600">
            {t('changes')}
          </AppText>
          {revision.changes.map((ch, i) => (
            <AppText key={i} muted size={13} style={{ writingDirection: 'ltr', textAlign: 'left' }}>
              • {ch}
            </AppText>
          ))}
        </View>
      ) : null}
      <Row>
        <Button title={t('approve')} small loading={decide.isPending} onPress={() => decide.mutate({ revisionId: revision.id, approve: true })} />
        <Button title={t('reject')} small variant="secondary" disabled={decide.isPending} onPress={() => decide.mutate({ revisionId: revision.id, approve: false })} />
      </Row>
      {decide.error ? <AppText style={{ color: c.danger, marginTop: space.sm }}>{decide.error.message}</AppText> : null}
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
