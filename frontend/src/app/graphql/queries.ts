/**
 * GraphQL queries for the application.
 *
 * These queries are used with graphql-request and React Query.
 */
import { gql } from 'graphql-request';

// Item queries with owner relationship
export const ITEMS_QUERY = gql`
  query Items($skip: Int, $limit: Int, $search: String, $sortBy: String, $sortOrder: String) {
    items(skip: $skip, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      id
      title
      description
      ownerId
      owner {
        id
        email
        username
        fullName
      }
    }
    itemsCount(search: $search)
  }
`;

export const ITEM_QUERY = gql`
  query Item($id: Int!) {
    item(id: $id) {
      id
      title
      description
      ownerId
      owner {
        id
        email
        username
        fullName
      }
    }
  }
`;

// User queries
export const USERS_QUERY = gql`
  query Users($skip: Int, $limit: Int) {
    users(skip: $skip, limit: $limit) {
      id
      email
      username
      fullName
      active
      admin
      createdAt
      lastLogin
    }
  }
`;

export const USER_QUERY = gql`
  query User($id: Int!) {
    user(id: $id) {
      id
      email
      username
      fullName
      active
      admin
      createdAt
      lastLogin
    }
  }
`;

export const ME_QUERY = gql`
  query Me {
    me {
      id
      email
      username
      fullName
      active
      admin
      createdAt
      lastLogin
    }
  }
`;
