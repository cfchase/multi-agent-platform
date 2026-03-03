/**
 * Chat API service for communicating with the backend.
 *
 * Adapted from reference chatbot to work with our persistent chat backend.
 */

import apiClient from '@app/api/apiClient';

const API_BASE = '/v1/chats';

// =============================================================================
// Types
// =============================================================================

export interface Chat {
  id: number;
  title: string;
  user_id: number;
  flow_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatCreate {
  title: string;
}

export interface ChatsResponse {
  data: Chat[];
  count: number;
}

export interface ChatMessage {
  id: number;
  chat_id: number;
  content: string;
  role: 'user' | 'assistant';
  created_at: string;
}

export interface ChatMessagesResponse {
  data: ChatMessage[];
  count: number;
}

/**
 * Discriminated union for streaming events.
 * Each event type has its own specific fields.
 */
export type StreamingEvent =
  | { type: 'content'; content: string }
  | { type: 'done'; message_id?: number }
  | { type: 'error'; error: string };

export interface Flow {
  id: string;
  name: string;
  description?: string;
}

export interface FlowsResponse {
  data: Flow[];
  count: number;
  default_flow?: string;
}

// =============================================================================
// Job Types
// =============================================================================

export type JobStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled' | 'timed_out';

export interface JobResponse {
  id: number;
  chat_message_id: number;
  langflow_job_id: string | null;
  flow_id: string | null;
  status: JobStatus;
  error_message: string | null;
  result_content: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Terminal statuses -- polling stops when job reaches one of these. */
export const TERMINAL_STATUSES: JobStatus[] = ['completed', 'failed', 'cancelled', 'timed_out'];

// =============================================================================
// Chat CRUD
// =============================================================================

export const ChatAPI = {
  async getChats(): Promise<ChatsResponse> {
    const response = await apiClient.get<ChatsResponse>(`${API_BASE}/`);
    return response.data;
  },

  async getFlows(): Promise<FlowsResponse> {
    const response = await apiClient.get<FlowsResponse>('/v1/flows/');
    return response.data;
  },

  async getChat(id: number): Promise<Chat> {
    const response = await apiClient.get<Chat>(`${API_BASE}/${id}`);
    return response.data;
  },

  async createChat(data: ChatCreate): Promise<Chat> {
    const response = await apiClient.post<Chat>(`${API_BASE}/`, data);
    return response.data;
  },

  async updateChat(id: number, data: Partial<ChatCreate>): Promise<Chat> {
    const response = await apiClient.put<Chat>(`${API_BASE}/${id}`, data);
    return response.data;
  },

  async deleteChat(id: number): Promise<void> {
    await apiClient.delete(`${API_BASE}/${id}`);
  },

  // ===========================================================================
  // Messages
  // ===========================================================================

  async getMessages(chatId: number): Promise<ChatMessagesResponse> {
    const response = await apiClient.get<ChatMessagesResponse>(
      `${API_BASE}/${chatId}/messages/`
    );
    return response.data;
  },

  // ===========================================================================
  // Jobs
  // ===========================================================================

  /**
   * Send a message and create a background job for AI processing.
   *
   * Returns the Job record. The frontend then polls GET /jobs/{id}?sync=true
   * until the job reaches a terminal state.
   */
  async createJobMessage(chatId: number, content: string, flowName?: string): Promise<JobResponse> {
    const body = flowName ? { content, flow_name: flowName } : { content };
    const response = await apiClient.post<JobResponse>(
      `${API_BASE}/${chatId}/messages/job`,
      body
    );
    return response.data;
  },

  /**
   * Get job status, optionally syncing with LangFlow first.
   *
   * When sync=true, the backend polls LangFlow V2 API before returning.
   */
  async getJob(jobId: number, sync: boolean = false): Promise<JobResponse> {
    const params = sync ? '?sync=true' : '';
    const response = await apiClient.get<JobResponse>(`/v1/jobs/${jobId}${params}`);
    return response.data;
  },

  /**
   * Cancel a running job.
   *
   * Calls LangFlow V2 stop endpoint and updates job status to cancelled.
   */
  async cancelJob(jobId: number): Promise<JobResponse> {
    const response = await apiClient.post<JobResponse>(`/v1/jobs/${jobId}/cancel`);
    return response.data;
  },

  /**
   * Get the active (non-terminal) job for a chat, if any.
   *
   * Used for page refresh recovery -- checks if there's an in-flight job
   * that the frontend should resume polling for.
   * Returns null (via 404) if no active job exists.
   */
  async getActiveJob(chatId: number): Promise<JobResponse | null> {
    try {
      const response = await apiClient.get<JobResponse>(
        `${API_BASE}/${chatId}/active-job`
      );
      return response.data;
    } catch {
      // 404 means no active job -- expected behavior
      return null;
    }
  },

  // ===========================================================================
  // Streaming (legacy, kept for backward compatibility)
  // ===========================================================================

  /**
   * Send a message and stream the AI response via SSE.
   *
   * Based on reference chatbot pattern using fetch + ReadableStream.
   * Uses flow_name for identification as flow IDs change on import.
   */
  createStreamingMessage(
    chatId: number,
    content: string,
    onMessage: (event: StreamingEvent) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void,
    flowName?: string
  ): { close: () => void } {
    const controller = new AbortController();
    const url = `/api${API_BASE}/${chatId}/messages/stream`;
    const body = flowName ? { content, flow_name: flowName } : { content };

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          let detail = `HTTP error! status: ${response.status}`;
          try {
            const body = await response.json();
            if (body?.detail) {
              detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
            }
          } catch {
            // Response body wasn't JSON — use default status message
          }
          throw new Error(detail);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        processSSEStream(reader, onMessage, onComplete, onError);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          onError?.(error);
        }
      });

    return { close: () => controller.abort() };
  },
};

async function processSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onMessage: (event: StreamingEvent) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        onComplete?.();
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const event of events) {
        if (!event.trim()) continue;
        parseSSEEvent(event, onMessage);
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name !== 'AbortError') {
      onError?.(error);
    }
  }
}

function parseSSEEvent(event: string, onMessage: (event: StreamingEvent) => void): void {
  const lines = event.split('\n');
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    try {
      const data = JSON.parse(line.slice(6));
      onMessage(data);
    } catch (e) {
      console.error('Error parsing SSE data:', e);
    }
  }
}
