/**
 * GraphQL response types.
 *
 * These types match the Strawberry GraphQL schema defined in the backend.
 */

export interface UserType {
  id: number;
  email: string;
  username: string | null;
  fullName: string | null;
  active: boolean;
  admin: boolean;
  createdAt: string;
  lastLogin: string;
}

export interface ItemType {
  id: number;
  title: string;
  description: string | null;
  ownerId: number;
  owner?: UserType;
}

export interface ItemsQueryResult {
  items: ItemType[];
  itemsCount: number;
}

export interface ItemQueryResult {
  item: ItemType | null;
}

export interface UsersQueryResult {
  users: UserType[];
}

export interface UserQueryResult {
  user: UserType | null;
}

export interface MeQueryResult {
  me: UserType | null;
}
