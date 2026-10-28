import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { useAnswerIntake, useFinishIntake, useGeneratePlan, useIntake } from '@/api/hooks';
import type { IntakeTurn } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { textDir } from '@/lib/text';
import { AppText, Button, Card, Chips, ErrorView, Field, Loading, Row, Screen } from '@/ui';
import { radius, space, useColors } from '@/ui/theme';

function Bubble({ text, mine }: { text: string; mine?: boolean }) {
  const c = useColors();
  return (
    <View
      style={{
        alignSelf: mine ? 'flex-end' : 'flex-start',
        backgroundColor: mine ? c.userBubble : c.botBubble,
        borderColor: c.border,
        borderWidth: mine ? 0 : 1,
        borderRadius: radius.lg,
        paddingVertical: 9,
        paddingHorizontal: 13,
        marginBottom: space.sm,
        maxWidth: '85%',
      }}>
      <AppText style={[{ color: mine ? c.userBubbleText : c.text }, textDir(text)]}>{text}</AppText>
    </View>
  );
}

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
  const asked = state.history.length + (state.current ? 1 : 0);

  return (
    <Screen>
      <AppText muted style={{ marginBottom: space.md }}>
        {t('intakeIntro')}
      </AppText>
      {state.history.map((turn) => (
        <View key={turn.id}>
          <Bubble text={turn.question} />
          <Bubble text={turn.skipped ? `— ${t('skip')} —` : (turn.answer ?? '')} mine />
        </View>
      ))}

      {state.current ? (
        <>
          <Bubble text={state.current.question} />
          {state.current.reason ? (
            <AppText muted size={12} style={{ marginBottom: space.md, ...textDir(state.current.reason) }}>
              {t('whyAsk', { reason: state.current.reason })}
            </AppText>
          ) : null}
          <Card>
            <AppText muted size={12} style={{ marginBottom: space.sm }}>
              {t('questionOf', { n: asked, max: state.max_questions })}
            </AppText>
            <AnswerInput
              key={state.current.id}
              turn={state.current}
              busy={answer.isPending}
              onSubmit={(a) => answer.mutate({ turn_id: state.current!.id, answer: a })}
            />
            <Row style={{ justifyContent: 'space-between', marginTop: space.md }}>
              <Button title={t('skip')} variant="ghost" small onPress={() => answer.mutate({ turn_id: state.current!.id, skip: true })} disabled={answer.isPending} />
              <Button title={t('enoughQuestions')} variant="ghost" small onPress={() => finish.mutate()} loading={finish.isPending} />
            </Row>
          </Card>
        </>
      ) : (
        <Card tone="primary">
          <AppText weight="700" style={{ marginBottom: space.sm }}>
            {t('intakeDone')}
          </AppText>
          {state.summary ? <AppText style={[{ marginBottom: space.md }, textDir(state.summary)]}>{state.summary}</AppText> : null}
          <Button
            title={generate.isPending ? t('buildingPlan') : t('buildPlan')}
            loading={generate.isPending}
            onPress={() => generate.mutate(undefined, { onSuccess: () => router.replace(`/goal/${goalId}`) })}
          />
        </Card>
      )}
      {answer.error || finish.error || generate.error ? (
        <AppText style={{ color: c.danger }}>{(answer.error ?? finish.error ?? generate.error)?.message}</AppText>
      ) : null}
    </Screen>
  );
}
