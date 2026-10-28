import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type {
  AppNotification,
  ChatMessage,
  ChatOut,
  Goal,
  GoalCreate,
  IntakeState,
  PlanOut,
  ProgressOut,
  Revision,
  TaskStatus,
  TodayOut,
  User,
} from './types';

export const keys = {
  goals: ['goals'] as const,
  goal: (id: number) => ['goal', id] as const,
  intake: (id: number) => ['goal', id, 'intake'] as const,
  plan: (id: number) => ['goal', id, 'plan'] as const,
  today: (id: number, date?: string) => ['goal', id, 'today', date ?? 'now'] as const,
  progress: (id: number) => ['goal', id, 'progress'] as const,
  revisions: (id: number) => ['goal', id, 'revisions'] as const,
  chat: (id: number) => ['goal', id, 'chat'] as const,
  notifications: ['notifications'] as const,
};

// ---- queries --------------------------------------------------------------------------------

export const useGoals = () => useQuery({ queryKey: keys.goals, queryFn: () => api<Goal[]>('/goals'), refetchInterval: 30_000 });

export const useGoal = (id: number) => useQuery({ queryKey: keys.goal(id), queryFn: () => api<Goal>(`/goals/${id}`) });

export const useIntake = (id: number) =>
  useQuery({ queryKey: keys.intake(id), queryFn: () => api<IntakeState>(`/goals/${id}/intake`) });

export const usePlan = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.plan(id), queryFn: () => api<PlanOut>(`/goals/${id}/plan`), enabled });

export const useToday = (id: number, date?: string, enabled = true) =>
  useQuery({
    queryKey: keys.today(id, date),
    queryFn: () => api<TodayOut>(`/goals/${id}/today`, { query: { date } }),
    enabled,
  });

export const useProgress = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.progress(id), queryFn: () => api<ProgressOut>(`/goals/${id}/progress`), enabled });

export const useRevisions = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.revisions(id), queryFn: () => api<Revision[]>(`/goals/${id}/revisions`), enabled });

/** The planner's answer to a change request: a proposal, an applied update, or a "no change needed" reply. */
export const revisionArrived = (messages: ChatMessage[] | undefined, afterId: number) =>
  !!messages?.some((m) => m.role === 'assistant' && m.id > afterId);

/** Polls every 10 s, or every 2 s while waiting for the planner's answer posted after message `waitAfterId`. */
export const useChat = (id: number, waitAfterId: number | null) =>
  useQuery({
    queryKey: keys.chat(id),
    queryFn: () => api<ChatMessage[]>(`/goals/${id}/chat`),
    refetchInterval: (query) =>
      waitAfterId !== null && !revisionArrived(query.state.data, waitAfterId) ? 2_000 : 10_000,
  });

export const useNotifications = () =>
  useQuery({
    queryKey: keys.notifications,
    queryFn: () => api<AppNotification[]>('/notifications'),
    refetchInterval: 15_000,
  });

// ---- mutations ------------------------------------------------------------------------------

function useInvalidateGoal(id: number) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['goal', id] });
    qc.invalidateQueries({ queryKey: keys.goals });
    qc.invalidateQueries({ queryKey: keys.notifications });
  };
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GoalCreate) => api<Goal>('/goals', { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.goals }),
  });
}

export function useUpdateGoal(id: number) {
  const invalidate = useInvalidateGoal(id);
  return useMutation({
    mutationFn: (body: Partial<GoalCreate> & { status?: string }) => api<Goal>(`/goals/${id}`, { method: 'PATCH', body }),
    onSuccess: invalidate,
  });
}

export function useDeleteGoal(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>(`/goals/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.goals }),
  });
}

export function useAnswerIntake(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { turn_id: number; answer?: string; skip?: boolean }) =>
      api<IntakeState>(`/goals/${id}/intake/answer`, { body }),
    onSuccess: (data) => qc.setQueryData(keys.intake(id), data),
  });
}

export function useFinishIntake(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<IntakeState>(`/goals/${id}/intake/finish`, { body: {} }),
    onSuccess: (data) => qc.setQueryData(keys.intake(id), data),
  });
}

export function useGeneratePlan(id: number) {
  const invalidate = useInvalidateGoal(id);
  return useMutation({ mutationFn: () => api<PlanOut>(`/goals/${id}/plan/generate`, { body: {} }), onSuccess: invalidate });
}

export function useLogTask(id: number) {
  const invalidate = useInvalidateGoal(id);
  return useMutation({
    mutationFn: (v: { taskId: string; date: string; status: TaskStatus }) =>
      api<TodayOut>(`/goals/${id}/tasks/${v.taskId}/log`, { body: { date: v.date, status: v.status } }),
    onSuccess: invalidate,
  });
}

export function useLogMetric(id: number) {
  const invalidate = useInvalidateGoal(id);
  return useMutation({
    mutationFn: (v: { key: string; value: number }) =>
      api<ProgressOut>(`/goals/${id}/metrics/${v.key}/log`, { body: { value: v.value } }),
    onSuccess: invalidate,
  });
}

export function useRequestRevision(id: number) {
  const invalidate = useInvalidateGoal(id);
  return useMutation({
    mutationFn: (message: string) => api<Revision | null>(`/goals/${id}/revisions/request`, { body: { message } }),
    onSuccess: invalidate,
  });
}

export function useDecideRevision(id: number) {
  const invalidate = useInvalidateGoal(id);
  return useMutation({
    mutationFn: (v: { revisionId: number; approve: boolean }) =>
      api<Revision>(`/goals/${id}/revisions/${v.revisionId}/${v.approve ? 'approve' : 'reject'}`, { body: {} }),
    onSuccess: invalidate,
    onError: invalidate,
  });
}

export function useSendMessage(id: number) {
  const qc = useQueryClient();
  const invalidate = useInvalidateGoal(id);
  return useMutation({
    mutationFn: (content: string) => api<ChatOut>(`/goals/${id}/chat`, { body: { content } }),
    onSuccess: (data) => {
      qc.setQueryData<ChatMessage[]>(keys.chat(id), (old) => [...(old ?? []), data.user_message, data.reply]);
      invalidate();
    },
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: number; goalId?: number }) =>
      v.id !== undefined
        ? api<void>(`/notifications/${v.id}/read`, { body: {} })
        : api<void>('/notifications/read-all', { body: {}, query: { goal_id: v.goalId } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.notifications });
      qc.invalidateQueries({ queryKey: keys.goals });
    },
  });
}

export function useUpdateMe() {
  return useMutation({
    mutationFn: (body: Partial<Pick<User, 'display_name' | 'language' | 'timezone'>>) =>
      api<User>('/me', { method: 'PATCH', body }),
  });
}

export function useDevTick() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (now?: string) => api<{ checkins: number; reviews: number }>('/dev/tick', { body: { now } }),
    onSuccess: () => qc.invalidateQueries(),
  });
}
