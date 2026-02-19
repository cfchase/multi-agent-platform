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
  // Streaming
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
