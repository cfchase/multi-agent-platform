import apiClient from '@app/api/apiClient';

export interface Item {
  id: number;
  title: string;
  description: string | null;
  owner_id: number;
}

export interface ItemCreate {
  title: string;
  description?: string;
}

export interface ItemUpdate {
  title?: string;
  description?: string;
}

export interface ItemsResponse {
  data: Item[];
  count: number;
}

export interface ItemsQueryParams {
  skip?: number;
  limit?: number;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

const API_BASE = '/v1/items';

export const itemService = {
  async getItems(params?: ItemsQueryParams): Promise<ItemsResponse> {
    const response = await apiClient.get<ItemsResponse>(`${API_BASE}/`, { params });
    return response.data;
  },

  async getItem(id: number): Promise<Item> {
    const response = await apiClient.get<Item>(`${API_BASE}/${id}`);
    return response.data;
  },

  async createItem(item: ItemCreate): Promise<Item> {
    const response = await apiClient.post<Item>(`${API_BASE}/`, item);
    return response.data;
  },

  async updateItem(id: number, item: ItemUpdate): Promise<Item> {
    const response = await apiClient.put<Item>(`${API_BASE}/${id}`, item);
    return response.data;
  },

  async deleteItem(id: number): Promise<void> {
    await apiClient.delete(`${API_BASE}/${id}`);
  },
};
