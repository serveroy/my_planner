import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { useAnswerIntake, useFinishIntake, useGeneratePlan, useIntake } from '@/api/hooks';
import type { IntakeTurn } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { Bubble } from '@/components/Bubble';
import { textDir } from '@/lib/text';
import { AppText, Button, Card, Chips, ErrorView, Field, Icon, Loading, ProgressBar, Row, Screen } from '@/ui';
import { space, useColors } from '@/ui/theme';

function AnswerInput({ turn, onSubmit, busy }: { turn: IntakeTurn; onSubmit: (answer: string) => void; busy: boolean }) {
  const { t } = useI18n();
  const [text, setText] = useState('');
  const [multi, setMulti] = useState<string[]>([]);

  if (turn.answer_type === 'boolean') {
    return (
      <Row>
        <Button title={t('yes')} onPress={() => onSubmit(t('yes'))} loading={busy} style={{ flex: 1 }} />
        <Button title={t('no')} onPress={() => onSubmit(t('no'))} variant="secondary" disabled={busy} style={{ flex: 1 }} />
      </Row>
    );
  }
  if (turn.answer_type === 'choice') {
    return <Chips options={turn.options.map((o) => ({ value: o, label: o }))} value="" onChange={(o) => !busy && onSubmit(o)} />;
  }
  if (turn.answer_type === 'multi_choice') {
    return (
      <>
        <Chips
          options={turn.options.map((o) => ({ value: o, label: o }))}
          value={multi}
          onChange={(o) => setMulti((m) => (m.includes(o) ? m.filter((x) => x !== o) : [...m, o]))}
        />
        <Button title={t('send')} onPress={() => onSubmit(multi.join(', '))} disabled={!multi.length} loading={busy} />
      </>
    );
  }
  const numeric = turn.answer_type === 'number';
  const send = () => text.trim() && onSubmit(numeric && turn.unit ? `${text.trim()} ${turn.unit}` : text.trim());
  return (
    <>
      <Field
        placeholder={turn.unit ? `${t('yourAnswer')} (${turn.unit})` : t('yourAnswer')}
        value={text}
        onChangeText={setText}
        keyboardType={numeric ? 'decimal-pad' : 'default'}
        multiline={!numeric}
        onSubmitEditing={send}
      />
      <Button title={t('send')} onPress={send} disabled={!text.trim()} loading={busy} />
    </>
  );
}

export default function Intake() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const goalId = Number(id);
  const { t } = useI18n();
  const c = useColors();
  const intake = useIntake(goalId);
  const answer = useAnswerIntake(goalId);
  const finish = useFinishIntake(goalId);
  const generate = useGeneratePlan(goalId);

  if (intake.isLoading) return <Loading />;
  if (intake.error || !intake.data) return <ErrorView error={intake.error} onRetry={intake.refetch} />;
  const state = intake.data;
  const current = state.current;
  const asked = state.history.length + (current ? 1 : 0);
  const error = answer.error ?? finish.error ?? generate.error;

  return (
    <Screen>
      <Row style={{ marginBottom: space.lg }}>
        <AppText muted size={12} style={{ flexShrink: 0 }}>
          {current ? t('questionOf', { n: asked, max: state.max_questions }) : t('intakeDone')}
        </AppText>
        <ProgressBar value={current ? asked / state.max_questions : 1} color={c.accent} />
      </Row>
      {state.history.length === 0 ? (
        <AppText muted size={13} style={{ marginBottom: space.md }}>
          {t('intakeIntro')}
        </AppText>
      ) : null}
      {state.history.map((turn) => (
        <View key={turn.id}>
          <Bubble text={turn.question} />
          <Bubble text={turn.skipped ? `— ${t('skip')} —` : (turn.answer ?? '')} mine />
        </View>
      ))}

      {current ? (
        <>
          <Bubble text={current.question} />
          {current.reason ? (
            <Row style={{ gap: 4, marginBottom: space.md, marginTop: 2 }}>
              <Icon name="info" size={12} color={c.faint} />
              <AppText size={12} style={[{ color: c.faint, flex: 1 }, textDir(current.reason)]}>
                {current.reason}
              </AppText>
            </Row>
          ) : null}
          <Card style={{ marginTop: space.sm }}>
            <AnswerInput key={current.id} turn={current} busy={answer.isPending} onSubmit={(a) => answer.mutate({ turn_id: current.id, answer: a })} />
            <Row style={{ justifyContent: 'space-between', marginTop: space.sm }}>
              <Button title={t('skip')} variant="ghost" small onPress={() => answer.mutate({ turn_id: current.id, skip: true })} disabled={answer.isPending} />
              <Button title={t('enoughQuestions')} variant="ghost" small onPress={() => finish.mutate()} loading={finish.isPending} />
            </Row>
          </Card>
        </>
      ) : (
        <Card tone="primary" style={{ marginTop: space.sm }}>
          <Row style={{ marginBottom: space.sm }}>
            <Icon name="check-circle" size={16} color={c.primary} />
            <AppText weight="600">{t('intakeDone')}</AppText>
          </Row>
          {state.summary ? <AppText size={13} style={[{ marginBottom: space.md }, textDir(state.summary)]}>{state.summary}</AppText> : null}
          <Button
            title={generate.isPending ? t('buildingPlan') : t('buildPlan')}
            loading={generate.isPending}
            onPress={() => generate.mutate(undefined, { onSuccess: () => router.replace(`/goal/${goalId}`) })}
          />
        </Card>
      )}
      {error ? <AppText size={13} style={{ color: c.danger }}>{error.message}</AppText> : null}
    </Screen>
  );
}
