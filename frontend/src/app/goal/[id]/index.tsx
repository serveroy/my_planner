import { Redirect, router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import {
  useGoal,
  useLogMetric,
  useLogTask,
  usePlan,
  useProgress,
  useRequestRevision,
  useRevisions,
  useToday,
} from '@/api/hooks';
import type { MetricProgress, Plan, PlanTask, TaskStatus, TodayTask, Weekday } from '@/api/types';
import { RevisionCard, RevisionStatus } from '@/components/RevisionCard';
import { useI18n } from '@/i18n/I18nContext';
import { addDays, formatDate, textDir, todayISO } from '@/lib/text';
import { AppText, Badge, Button, Card, ErrorView, Field, Loading, ProgressBar, Row, Screen, SectionTitle } from '@/ui';
import { radius, space, useColors } from '@/ui/theme';

const DAY_NAMES: Record<'en' | 'he', Record<Weekday, string>> = {
  en: { sun: 'Sun', mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat' },
  he: { sun: 'א׳', mon: 'ב׳', tue: 'ג׳', wed: 'ד׳', thu: 'ה׳', fri: 'ו׳', sat: 'ש׳' },
};

function scheduleText(task: PlanTask, lang: 'en' | 'he', t: ReturnType<typeof useI18n>['t']) {
  const s = task.schedule;
  let text = '';
  if (s.type === 'weekly') text = s.days_of_week.map((d) => DAY_NAMES[lang][d]).join(' · ');
  else if (s.type === 'daily') text = lang === 'he' ? 'כל יום' : 'Every day';
  else if (s.type === 'every_n_days') text = lang === 'he' ? `כל ${s.interval_days} ימים` : `Every ${s.interval_days} days`;
  else if (s.date) text = formatDate(s.date, lang);
  return task.duration_minutes ? `${text} · ${t('minutes', { n: task.duration_minutes })}` : text;
}

function StatusButton({ label, active, color, onPress }: { label: string; active: boolean; color: string; onPress: () => void }) {
  const c = useColors();
  return (
    <Pressable
      onPress={onPress}
      style={{
        paddingVertical: 5,
        paddingHorizontal: 9,
        borderRadius: radius.sm,
        borderWidth: 1,
        borderColor: active ? color : c.border,
        backgroundColor: active ? color : 'transparent',
      }}>
      <AppText size={12} weight="600" style={{ color: active ? '#fff' : c.muted }}>
        {label}
      </AppText>
    </Pressable>
  );
}

function TodaySection({ goalId }: { goalId: number }) {
  const { t, lang } = useI18n();
  const c = useColors();
  const [day, setDay] = useState(todayISO());
  const today = useToday(goalId, day);
  const log = useLogTask(goalId);
  const isToday = day === todayISO();
  const setStatus = (task: TodayTask, status: TaskStatus) =>
    log.mutate({ taskId: task.task_id, date: day, status: task.status === status ? 'pending' : status }, { onSuccess: () => today.refetch() });

  return (
    <>
      <SectionTitle
        right={
          <Row>
            <Button title="‹" small variant="ghost" onPress={() => setDay(addDays(day, -1))} />
            <AppText muted size={13}>
              {isToday ? t('today') : formatDate(day, lang)}
            </AppText>
            <Button title="›" small variant="ghost" onPress={() => setDay(addDays(day, 1))} disabled={isToday} />
          </Row>
        }>
        {t('today')}
      </SectionTitle>
      <Card>
        {today.isLoading ? (
          <AppText muted>{t('loading')}</AppText>
        ) : !today.data?.tasks.length ? (
          <AppText muted>{t('noTasksToday')}</AppText>
        ) : (
          today.data.tasks.map((task) => (
            <View key={task.task_id} style={{ paddingVertical: space.sm, borderBottomWidth: 1, borderBottomColor: c.border }}>
              <Row style={{ justifyContent: 'space-between' }}>
                <View style={{ flex: 1 }}>
                  <AppText weight="600" style={[task.status === 'done' && { textDecorationLine: 'line-through', color: c.muted }, textDir(task.title)]}>
                    {task.title}
                  </AppText>
                  {task.duration_minutes ? (
                    <AppText muted size={12}>
                      {t('minutes', { n: task.duration_minutes })}
                    </AppText>
                  ) : null}
                </View>
                <Row style={{ gap: 6 }}>
                  <StatusButton label={t('done')} active={task.status === 'done'} color={c.success} onPress={() => setStatus(task, 'done')} />
                  <StatusButton label={t('partial')} active={task.status === 'partial'} color={c.warning} onPress={() => setStatus(task, 'partial')} />
                  <StatusButton label={t('skipped')} active={task.status === 'skipped'} color={c.danger} onPress={() => setStatus(task, 'skipped')} />
                </Row>
              </Row>
            </View>
          ))
        )}
      </Card>
    </>
  );
}

function MetricRow({ goalId, metric }: { goalId: number; metric: MetricProgress }) {
  const { t } = useI18n();
  const logMetric = useLogMetric(goalId);
  const [value, setValue] = useState('');
  const fmt = (v: number | null) => (v === null ? '—' : `${v} ${metric.unit}`.trim());
  return (
    <View style={{ marginBottom: space.md }}>
      <AppText weight="600">{metric.name}</AppText>
      <AppText muted size={13}>
        {t('latest')}: {fmt(metric.latest ?? metric.baseline)} · {t('target')}: {fmt(metric.target)}
      </AppText>
      <Row style={{ marginTop: space.xs }}>
        <View style={{ flex: 1 }}>
          <Field value={value} onChangeText={setValue} keyboardType="decimal-pad" placeholder={metric.unit} style={{ paddingVertical: 6 }} />
        </View>
        <Button
          title={t('logValue')}
          small
          disabled={!value || isNaN(Number(value))}
          loading={logMetric.isPending}
          onPress={() => logMetric.mutate({ key: metric.key, value: Number(value) }, { onSuccess: () => setValue('') })}
          style={{ marginBottom: space.md }}
        />
      </Row>
    </View>
  );
}

function ProgressSection({ goalId }: { goalId: number }) {
  const { t } = useI18n();
  const progress = useProgress(goalId);
  const r = progress.data?.report;
  if (!r) return null;
  return (
    <>
      <SectionTitle>{t('progress')}</SectionTitle>
      <Card>
        <Row style={{ justifyContent: 'space-between', marginBottom: space.md }}>
          <View>
            <AppText muted size={12}>{t('streak')}</AppText>
            <AppText size={20} weight="700">{t('streakDays', { n: r.streak_days })}</AppText>
          </View>
          <View>
            <AppText muted size={12}>{t('remaining')}</AppText>
            <AppText size={20} weight="700">{r.days_left}</AppText>
          </View>
        </Row>
        <AppText muted size={12}>
          {t('adherence')}: {r.adherence_7d === null ? '—' : `${Math.round(r.adherence_7d * 100)}%`}
        </AppText>
        <Row style={{ marginTop: 4, marginBottom: r.metrics.length ? space.lg : 0 }}>
          <ProgressBar value={r.adherence_7d ?? 0} />
        </Row>
        {r.metrics.map((m) => (
          <MetricRow key={m.key} goalId={goalId} metric={m} />
        ))}
      </Card>
    </>
  );
}

function PlanSection({ plan, version }: { plan: Plan; version: number }) {
  const { t, lang } = useI18n();
  return (
    <>
      <SectionTitle right={<Badge text={t('planVersion', { n: version })} tone="muted" />}>{t('plan')}</SectionTitle>
      <Card>
        <AppText style={[{ marginBottom: space.md }, textDir(plan.summary)]}>{plan.summary}</AppText>
        <AppText weight="700" style={{ marginBottom: space.xs }}>{t('tasks')}</AppText>
        {plan.tasks.map((task) => (
          <View key={task.id} style={{ marginBottom: space.sm }}>
            <AppText weight="600" style={textDir(task.title)}>{task.title}</AppText>
            <AppText muted size={13}>{scheduleText(task, lang, t)}</AppText>
            {task.description ? <AppText muted size={13} style={textDir(task.description)}>{task.description}</AppText> : null}
          </View>
        ))}
        <AppText weight="700" style={{ marginTop: space.md, marginBottom: space.xs }}>{t('milestones')}</AppText>
        {plan.milestones.map((m) => (
          <View key={m.id} style={{ marginBottom: space.sm }}>
            <AppText weight="600" style={textDir(m.title)}>{m.title} · {formatDate(m.target_date, lang)}</AppText>
            {m.success_criteria ? <AppText muted size={13} style={textDir(m.success_criteria)}>{m.success_criteria}</AppText> : null}
          </View>
        ))}
        {([['tips', plan.tips], ['safetyNotes', plan.safety_notes], ['assumptions', plan.assumptions]] as const).map(([key, items]) =>
          items.length ? (
            <View key={key} style={{ marginTop: space.md }}>
              <AppText weight="700" style={{ marginBottom: space.xs }}>{t(key)}</AppText>
              {items.map((it, i) => (
                <AppText key={i} muted size={13} style={textDir(it)}>• {it}</AppText>
              ))}
            </View>
          ) : null,
        )}
      </Card>
    </>
  );
}

function RequestChange({ goalId }: { goalId: number }) {
  const { t } = useI18n();
  const c = useColors();
  const request = useRequestRevision(goalId);
  const [text, setText] = useState('');
  return (
    <>
      <SectionTitle>{t('requestChange')}</SectionTitle>
      <Card>
        <Field value={text} onChangeText={setText} placeholder={t('requestChangePh')} multiline />
        <Button title={t('send')} disabled={text.trim().length < 2} loading={request.isPending}
          onPress={() => request.mutate(text.trim(), { onSuccess: () => setText('') })} />
        {request.isSuccess ? <AppText muted style={{ marginTop: space.sm }}>{request.data ? t('requestSent') : t('noChangeNeeded')}</AppText> : null}
        {request.error ? <AppText style={{ color: c.danger, marginTop: space.sm }}>{request.error.message}</AppText> : null}
      </Card>
    </>
  );
}

export default function GoalDashboard() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const goalId = Number(id);
  const { t, lang } = useI18n();
  const goal = useGoal(goalId);
  const hasPlan = !!goal.data?.current_plan_version;
  const plan = usePlan(goalId, hasPlan);
  const revisions = useRevisions(goalId, hasPlan);

  if (goal.isLoading) return <Loading />;
  if (goal.error || !goal.data) return <ErrorView error={goal.error} onRetry={goal.refetch} />;
  if (!hasPlan) return <Redirect href={`/goal/${goalId}/intake`} />;
  const pending = revisions.data?.find((r) => r.status === 'pending');
  const history = revisions.data?.filter((r) => r.status !== 'pending') ?? [];

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: goal.data.title,
          headerRight: () => (
            <Row style={{ paddingHorizontal: space.sm }}>
              <Button title={`💬 ${t('chat')}`} small variant="secondary" onPress={() => router.push(`/goal/${goalId}/chat`)} />
              <Button title="⚙️" small variant="ghost" onPress={() => router.push(`/goal/${goalId}/settings`)} />
            </Row>
          ),
        }}
      />
      {pending ? <RevisionCard goalId={goalId} revision={pending} /> : null}
      <TodaySection goalId={goalId} />
      <ProgressSection goalId={goalId} />
      {plan.data ? <PlanSection plan={plan.data.plan} version={plan.data.version} /> : null}
      <RequestChange goalId={goalId} />
      {history.length ? (
        <>
          <SectionTitle>{t('history')}</SectionTitle>
          {history.map((r) => (
            <Card key={r.id}>
              <Row style={{ justifyContent: 'space-between', marginBottom: space.xs }}>
                <RevisionStatus status={r.status} />
                <AppText muted size={12}>{formatDate(r.created_at, lang)}</AppText>
              </Row>
              <AppText size={14} style={textDir(r.explanation)}>{r.explanation}</AppText>
            </Card>
          ))}
        </>
      ) : null}
      <View style={{ height: space.xl }} />
    </Screen>
  );
}
