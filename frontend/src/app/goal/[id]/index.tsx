import { Redirect, router, Stack, useLocalSearchParams } from 'expo-router';
import { Fragment, useState } from 'react';
import { Pressable, TextInput, View } from 'react-native';

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
import {
  AppText,
  Button,
  Card,
  Divider,
  ErrorView,
  Icon,
  IconButton,
  type IconName,
  Loading,
  ProgressBar,
  Row,
  Screen,
  SectionTitle,
} from '@/ui';
import { fonts, radius, space, useColors } from '@/ui/theme';

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

// ---- stats ------------------------------------------------------------------------------------

function Stat({ icon, value, label, color }: { icon: IconName; value: string; label: string; color: string }) {
  return (
    <View style={{ flex: 1, alignItems: 'center', gap: 2 }}>
      <Icon name={icon} size={16} color={color} />
      <AppText size={18} weight="600">{value}</AppText>
      <AppText muted size={11}>{label}</AppText>
    </View>
  );
}

function StatsStrip({ goalId }: { goalId: number }) {
  const { t } = useI18n();
  const c = useColors();
  const r = useProgress(goalId).data?.report;
  if (!r) return null;
  return (
    <Card style={{ flexDirection: 'row', paddingVertical: space.md }}>
      <Stat icon="zap" value={String(r.streak_days)} label={t('streak')} color={c.accent} />
      <Stat icon="activity" value={r.adherence_7d === null ? '—' : `${Math.round(r.adherence_7d * 100)}%`} label={t('adherence')} color={c.primary} />
      <Stat icon="calendar" value={String(r.days_left)} label={t('remaining')} color={c.warning} />
    </Card>
  );
}

// ---- today ------------------------------------------------------------------------------------

function StatusDot({ active, color, onPress, label, children }: { active: boolean; color: string; onPress: () => void; label: string; children: React.ReactNode }) {
  const c = useColors();
  return (
    <Pressable
      onPress={onPress}
      accessibilityLabel={label}
      hitSlop={4}
      style={{
        width: 26,
        height: 26,
        borderRadius: 13,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: active ? color : 'transparent',
        borderWidth: active ? 0 : 1.5,
        borderColor: c.border,
      }}>
      {children}
    </Pressable>
  );
}

function TaskRow({ task, onSet }: { task: TodayTask; onSet: (s: TaskStatus) => void }) {
  const { t } = useI18n();
  const c = useColors();
  const done = task.status === 'done';
  const toggle = (s: TaskStatus) => onSet(task.status === s ? 'pending' : s);
  return (
    <Row style={{ paddingVertical: space.md, gap: space.md }}>
      <StatusDot active={done} color={c.success} onPress={() => toggle('done')} label={t('done')}>
        <Icon name="check" size={15} color={done ? '#fff' : c.faint} />
      </StatusDot>
      <View style={{ flex: 1 }}>
        <AppText weight="500" style={[done && { color: c.muted, textDecorationLine: 'line-through' }, textDir(task.title)]}>
          {task.title}
        </AppText>
        {task.duration_minutes ? <AppText muted size={12}>{t('minutes', { n: task.duration_minutes })}</AppText> : null}
      </View>
      <StatusDot active={task.status === 'partial'} color={c.warning} onPress={() => toggle('partial')} label={t('partial')}>
        <AppText size={12} weight="600" style={{ color: task.status === 'partial' ? '#fff' : c.faint, lineHeight: 14 }}>½</AppText>
      </StatusDot>
      <StatusDot active={task.status === 'skipped'} color={c.danger} onPress={() => toggle('skipped')} label={t('skipped')}>
        <Icon name="x" size={13} color={task.status === 'skipped' ? '#fff' : c.faint} />
      </StatusDot>
    </Row>
  );
}

function TodaySection({ goalId }: { goalId: number }) {
  const { t, lang, isRTL } = useI18n();
  const [day, setDay] = useState(todayISO());
  const today = useToday(goalId, day);
  const log = useLogTask(goalId);
  const isToday = day === todayISO();
  const tasks = today.data?.tasks ?? [];

  return (
    <>
      <SectionTitle
        right={
          <Row style={{ gap: 0 }}>
            <IconButton name={isRTL ? 'chevron-right' : 'chevron-left'} label="previous day" onPress={() => setDay(addDays(day, -1))} />
            <AppText muted size={12} style={{ minWidth: 70, textAlign: 'center' }}>
              {isToday ? t('today') : formatDate(day, lang)}
            </AppText>
            {isToday ? (
              <View style={{ width: 32 }} />
            ) : (
              <IconButton name={isRTL ? 'chevron-left' : 'chevron-right'} label="next day" onPress={() => setDay(addDays(day, 1))} />
            )}
          </Row>
        }>
        {t('today')}
      </SectionTitle>
      <Card style={{ paddingVertical: tasks.length ? 0 : space.md }}>
        {today.isLoading ? (
          <AppText muted size={13}>{t('loading')}</AppText>
        ) : !tasks.length ? (
          <AppText muted size={13}>{t('noTasksToday')}</AppText>
        ) : (
          tasks.map((task, i) => (
            <Fragment key={task.task_id}>
              {i > 0 ? <Divider /> : null}
              <TaskRow task={task} onSet={(status) => log.mutate({ taskId: task.task_id, date: day, status }, { onSuccess: () => today.refetch() })} />
            </Fragment>
          ))
        )}
      </Card>
    </>
  );
}

// ---- measurements -----------------------------------------------------------------------------

function MetricRow({ goalId, metric }: { goalId: number; metric: MetricProgress }) {
  const { t } = useI18n();
  const c = useColors();
  const logMetric = useLogMetric(goalId);
  const [value, setValue] = useState('');
  const fmt = (v: number | null) => (v === null ? '—' : `${v}`);
  const current = metric.latest ?? metric.baseline;
  const span = metric.baseline !== null && metric.target !== null ? metric.target - metric.baseline : null;
  const done = span && current !== null && metric.baseline !== null ? (current - metric.baseline) / span : 0;
  const valid = value !== '' && !isNaN(Number(value));
  const submit = () => valid && logMetric.mutate({ key: metric.key, value: Number(value) }, { onSuccess: () => setValue('') });
  return (
    <View style={{ paddingVertical: space.md, gap: 6 }}>
      <Row style={{ justifyContent: 'space-between' }}>
        <AppText weight="500">{metric.name}</AppText>
        <AppText muted size={12}>
          {fmt(current)} → {fmt(metric.target)} {metric.unit}
        </AppText>
      </Row>
      <ProgressBar value={done} />
      <Row>
        <TextInput
          value={value}
          onChangeText={setValue}
          keyboardType="decimal-pad"
          placeholder={`${t('logValue')} (${metric.unit})`}
          placeholderTextColor={c.faint}
          onSubmitEditing={submit}
          style={{ flex: 1, backgroundColor: c.fill, borderRadius: radius.sm, paddingHorizontal: 10, paddingVertical: 6, color: c.text, fontFamily: fonts['400'], fontSize: 13 }}
        />
        <Button icon="plus" small variant="secondary" disabled={!valid} loading={logMetric.isPending} onPress={submit} />
      </Row>
    </View>
  );
}

function MetricsSection({ goalId }: { goalId: number }) {
  const { t } = useI18n();
  const metrics = useProgress(goalId).data?.report.metrics ?? [];
  if (!metrics.length) return null;
  return (
    <>
      <SectionTitle>{t('metrics')}</SectionTitle>
      <Card style={{ paddingVertical: 0 }}>
        {metrics.map((m, i) => (
          <Fragment key={m.key}>
            {i > 0 ? <Divider /> : null}
            <MetricRow goalId={goalId} metric={m} />
          </Fragment>
        ))}
      </Card>
    </>
  );
}

// ---- plan -------------------------------------------------------------------------------------

function PlanSection({ plan, version }: { plan: Plan; version: number }) {
  const { t, lang } = useI18n();
  const c = useColors();
  const [more, setMore] = useState(false);
  const extras = ([['tips', plan.tips], ['safetyNotes', plan.safety_notes], ['assumptions', plan.assumptions]] as const).filter(([, items]) => items.length);
  return (
    <>
      <SectionTitle right={<AppText size={11} style={{ color: c.faint }}>{t('planVersion', { n: version })}</AppText>}>{t('plan')}</SectionTitle>
      <Card>
        <AppText size={13} style={[{ marginBottom: space.md }, textDir(plan.summary)]}>{plan.summary}</AppText>
        {plan.tasks.map((task) => (
          <Row key={task.id} style={{ alignItems: 'flex-start', marginBottom: space.sm }}>
            <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: c.primary, marginTop: 7 }} />
            <View style={{ flex: 1 }}>
              <AppText weight="500" style={textDir(task.title)}>{task.title}</AppText>
              <AppText muted size={12}>{scheduleText(task, lang, t)}</AppText>
            </View>
          </Row>
        ))}
        <Divider />
        <AppText muted size={12} weight="500" style={{ marginTop: space.md, marginBottom: space.sm }}>{t('milestones')}</AppText>
        {plan.milestones.map((m, i) => (
          <Row key={m.id} style={{ alignItems: 'flex-start' }}>
            <View style={{ alignItems: 'center', width: 12 }}>
              <View style={{ width: 9, height: 9, borderRadius: 5, borderWidth: 2, borderColor: c.accent, marginTop: 5 }} />
              {i < plan.milestones.length - 1 ? <View style={{ width: 2, flex: 1, minHeight: 18, backgroundColor: c.border }} /> : null}
            </View>
            <Row style={{ flex: 1, justifyContent: 'space-between', paddingBottom: space.sm }}>
              <AppText size={13} style={[{ flex: 1 }, textDir(m.title)]}>{m.title}</AppText>
              <AppText muted size={12}>{formatDate(m.target_date, lang)}</AppText>
            </Row>
          </Row>
        ))}
        {extras.length ? (
          <>
            {more
              ? extras.map(([key, items]) => (
                  <View key={key} style={{ marginTop: space.sm }}>
                    <AppText muted size={12} weight="500" style={{ marginBottom: 2 }}>{t(key)}</AppText>
                    {items.map((it, i) => (
                      <AppText key={i} size={13} style={textDir(it)}>• {it}</AppText>
                    ))}
                  </View>
                ))
              : null}
            <Button title={more ? t('showLess') : t('showMore')} variant="ghost" small onPress={() => setMore(!more)} style={{ alignSelf: 'flex-start', marginTop: space.xs, paddingHorizontal: 0 }} />
          </>
        ) : null}
      </Card>
    </>
  );
}

function RequestChange({ goalId }: { goalId: number }) {
  const { t, isRTL } = useI18n();
  const c = useColors();
  const request = useRequestRevision(goalId);
  const [text, setText] = useState('');
  const submit = () => text.trim().length >= 2 && request.mutate(text.trim(), { onSuccess: () => setText('') });
  return (
    <>
      <SectionTitle>{t('requestChange')}</SectionTitle>
      <Card>
        <Row>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder={t('requestChangePh')}
            placeholderTextColor={c.faint}
            onSubmitEditing={submit}
            style={[{ flex: 1, backgroundColor: c.fill, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 9, color: c.text, fontFamily: fonts['400'], fontSize: 14 }, textDir(text || t('requestChangePh'))]}
          />
          <Button icon={isRTL ? 'arrow-left' : 'arrow-right'} onPress={submit} disabled={text.trim().length < 2} loading={request.isPending} style={{ paddingHorizontal: 12 }} />
        </Row>
        {request.isSuccess ? <AppText muted size={12} style={{ marginTop: space.sm }}>{request.data ? t('requestSent') : t('noChangeNeeded')}</AppText> : null}
        {request.error ? <AppText size={12} style={{ color: c.danger, marginTop: space.sm }}>{request.error.message}</AppText> : null}
      </Card>
    </>
  );
}

// ---- screen -----------------------------------------------------------------------------------

export default function GoalDashboard() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const goalId = Number(id);
  const { t, lang } = useI18n();
  const c = useColors();
  const goal = useGoal(goalId);
  const hasPlan = !!goal.data?.current_plan_version;
  const plan = usePlan(goalId, hasPlan);
  const revisions = useRevisions(goalId, hasPlan);
  const [showHistory, setShowHistory] = useState(false);

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
            <Row style={{ gap: 4 }}>
              <IconButton
                name="message-circle"
                label={t('chat')}
                color={c.primary}
                badge={goal.data.unread_notifications > 0}
                onPress={() => router.push(`/goal/${goalId}/chat`)}
              />
              <IconButton name="sliders" label={t('goalSettings')} onPress={() => router.push(`/goal/${goalId}/settings`)} />
            </Row>
          ),
        }}
      />
      {pending ? <RevisionCard goalId={goalId} revision={pending} /> : null}
      <StatsStrip goalId={goalId} />
      <TodaySection goalId={goalId} />
      <MetricsSection goalId={goalId} />
      {plan.data ? <PlanSection plan={plan.data.plan} version={plan.data.version} /> : null}
      <RequestChange goalId={goalId} />
      {history.length ? (
        <>
          <SectionTitle right={<Button title={showHistory ? t('showLess') : t('showMore')} variant="ghost" small onPress={() => setShowHistory(!showHistory)} />}>
            {t('history')} ({history.length})
          </SectionTitle>
          {showHistory ? (
            <Card style={{ paddingVertical: 0 }}>
              {history.map((r, i) => (
                <Fragment key={r.id}>
                  {i > 0 ? <Divider /> : null}
                  <View style={{ paddingVertical: space.md, gap: 4 }}>
                    <Row style={{ justifyContent: 'space-between' }}>
                      <RevisionStatus status={r.status} />
                      <AppText muted size={11}>{formatDate(r.created_at, lang)}</AppText>
                    </Row>
                    <AppText size={13} style={textDir(r.explanation)}>{r.explanation}</AppText>
                  </View>
                </Fragment>
              ))}
            </Card>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}
