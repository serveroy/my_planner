// Mirrors backend/src/planner/api/schemas.py and llm/contracts.py.

export type Lang = 'en' | 'he';
export type Weekday = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';
export type TimeOfDay = 'morning' | 'afternoon' | 'evening' | 'any';
export type UpdateMode = 'auto' | 'ask';
export type TaskStatus = 'pending' | 'done' | 'partial' | 'skipped';

export interface User {
  id: number;
  email: string;
  display_name: string;
  language: Lang;
  timezone: string;
}

export interface TokenOut {
  access_token: string;
  user: User;
}

export interface AvailableTime {
  minutes_per_day: number;
  days_per_week: number;
  preferred_days: Weekday[];
  preferred_time_of_day: TimeOfDay;
  notes: string;
}

export interface AnswerFormat {
  language: Lang | 'auto';
  verbosity: 'concise' | 'balanced' | 'detailed';
  tone: 'warm' | 'direct' | 'motivational';
  style: 'bullets' | 'paragraphs' | 'mixed';
  use_emojis: boolean;
  notes: string;
}

export interface CheckinSettings {
  enabled: boolean;
  daily_time: string;
  max_per_day: number;
  quiet_start: string;
  quiet_end: string;
  inactivity_days: number;
}

export interface SafetyFlag {
  code: string;
  severity: 'info' | 'caution' | 'high';
  guidance: string;
}

export type GoalStatus = 'intake' | 'planning' | 'active' | 'paused' | 'completed' | 'archived';

export interface Goal {
  id: number;
  title: string;
  description: string;
  current_state: string;
  deadline: string;
  available_time: AvailableTime;
  answer_format: AnswerFormat;
  extra_context: string;
  update_mode: UpdateMode;
  checkin_settings: CheckinSettings;
  status: GoalStatus;
  intake_summary: string;
  profile: Record<string, unknown>;
  safety_flags: SafetyFlag[];
  constraints: { text: string; since: string }[];
  current_plan_version: number | null;
  created_at: string;
  has_pending_revision: boolean;
  unread_notifications: number;
}

export interface GoalCreate {
  title: string;
  description: string;
  current_state: string;
  deadline: string;
  available_time: AvailableTime;
  answer_format: AnswerFormat;
  extra_context: string;
  update_mode: UpdateMode;
  checkin_settings: CheckinSettings;
}

export type AnswerType = 'text' | 'number' | 'choice' | 'multi_choice' | 'date' | 'boolean';

export interface IntakeTurn {
  id: number;
  index: number;
  question: string;
  field: string;
  answer_type: AnswerType;
  options: string[];
  unit: string | null;
  reason: string | null;
  answer: string | null;
  skipped: boolean;
}

export interface IntakeState {
  status: 'in_progress' | 'finished';
  current: IntakeTurn | null;
  history: IntakeTurn[];
  summary: string;
  max_questions: number;
}

export interface TaskSchedule {
  type: 'once' | 'daily' | 'weekly' | 'every_n_days';
  date?: string | null;
  days_of_week: Weekday[];
  interval_days?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  time_of_day: TimeOfDay;
}

export interface PlanTask {
  id: string;
  title: string;
  description: string;
  milestone_id: string | null;
  schedule: TaskSchedule;
  duration_minutes: number | null;
  metric_key: string | null;
}

export interface Milestone {
  id: string;
  title: string;
  description: string;
  target_date: string;
  success_criteria: string;
}

export interface Metric {
  key: string;
  name: string;
  unit: string;
  baseline: number | null;
  target: number | null;
  direction: 'increase' | 'decrease' | 'maintain';
}

export interface Plan {
  title: string;
  summary: string;
  start_date: string;
  end_date: string;
  milestones: Milestone[];
  tasks: PlanTask[];
  metrics: Metric[];
  tips: string[];
  safety_notes: string[];
  assumptions: string[];
}

export interface PlanOut {
  version: number;
  source: string;
  created_at: string;
  plan: Plan;
  warnings: string[];
}

export interface TodayTask {
  task_id: string;
  title: string;
  duration_minutes: number | null;
  time_of_day: TimeOfDay;
  status: TaskStatus;
}

export interface TodayOut {
  date: string;
  tasks: TodayTask[];
}

export interface MetricProgress {
  key: string;
  name: string;
  unit: string;
  baseline: number | null;
  target: number | null;
  direction: string;
  latest: number | null;
  latest_date: string | null;
  expected_now: number | null;
}

export interface MilestoneStatus {
  id: string;
  title: string;
  target_date: string;
  status: 'upcoming' | 'due_soon' | 'overdue' | 'passed';
}

export interface ProgressReport {
  as_of: string;
  days_elapsed: number;
  days_left: number;
  adherence_7d: number | null;
  adherence_28d: number | null;
  streak_days: number;
  tasks: { task_id: string; title: string; due: number; done: number; adherence: number | null }[];
  metrics: MetricProgress[];
  milestones: MilestoneStatus[];
}

export interface ProgressOut {
  report: ProgressReport;
  metric_history: Record<string, { date: string; value: number }[]>;
}

export interface Revision {
  id: number;
  trigger: string;
  trigger_details: string;
  explanation: string;
  operations: Record<string, unknown>[];
  changes: string[];
  status: 'pending' | 'applied' | 'rejected' | 'superseded';
  base_version: number;
  new_version: number | null;
  created_at: string;
  decided_at: string | null;
}

export type MessageKind = 'chat' | 'checkin' | 'plan_ready' | 'revision_proposal' | 'revision_applied' | 'safety';

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  kind: MessageKind;
  content: string;
  meta: { revision_id?: number; decision?: string; trigger?: string; actions?: string[] } & Record<string, unknown>;
  created_at: string;
}

export interface ChatOut {
  user_message: ChatMessage;
  reply: ChatMessage;
  actions: string[];
  revision_in_progress: boolean;
}

export interface AppNotification {
  id: number;
  goal_id: number | null;
  type: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}
