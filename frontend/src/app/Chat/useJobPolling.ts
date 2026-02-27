/**
 * TanStack Query hook for polling job status.
 *
 * Polls GET /jobs/{id}?sync=true every 5s while the job is active.
 * Stops polling automatically when the job reaches a terminal state
 * (completed, failed, cancelled, timed_out).
 *
 * Based on the tang-web-app useJobsByBranch pattern with refetchInterval callback.
 */

import { useQuery } from '@tanstack/react-query';
import { ChatAPI, JobResponse, TERMINAL_STATUSES } from './chatApi';

export function useJobPolling(jobId: number | null) {
  return useQuery<JobResponse>({
    queryKey: ['job', jobId],
    queryFn: async () => {
      // Always sync with LangFlow on poll (backend skips sync for terminal states)
      return ChatAPI.getJob(jobId!, true);
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return 5000;
      const isTerminal = TERMINAL_STATUSES.includes(job.status);
      return isTerminal ? false : 5000;
    },
    // Just under 5s to prevent extra refetches between polls
    staleTime: 4000,
  });
}
