import type { Goal } from '@/api/types';

/** Where tapping a goal (or its notification) should go, depending on its stage. */
export function goalHref(goal: Pick<Goal, 'id' | 'status'>) {
  return goal.status === 'intake' || goal.status === 'planning'
    ? (`/goal/${goal.id}/intake` as const)
    : (`/goal/${goal.id}` as const);
}
