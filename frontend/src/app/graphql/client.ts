/**
 * GraphQL client configuration.
 *
 * Uses graphql-request for lightweight GraphQL queries that integrate
 * well with React Query.
 *
 * Example usage:
 * ```typescript
 * import { executeGraphQLQuery } from './graphql/client';
 *
 * const data = await executeGraphQLQuery<ItemsQueryResult>(ITEMS_QUERY, {
 *   skip: 0,
 *   limit: 10,
 * });
 * ```
 */
import { GraphQLClient, Variables } from 'graphql-request';

// GraphQL endpoint - use absolute URL for graphql-request v7 compatibility
// window.location.origin provides the base URL (e.g., http://localhost:8080)
const endpoint = `${window.location.origin}/api/graphql`;

export const graphqlClient = new GraphQLClient(endpoint, {
  // Headers will be passed through by the OAuth2 proxy
  credentials: 'include',
});

/**
 * Execute a GraphQL query with type-safe response.
 *
 * This helper provides:
 * - Type inference for the response data
 * - Consistent error handling
 * - Easy integration with React Query
 *
 * @param query - GraphQL query string
 * @param variables - Query variables (optional)
 * @returns Promise resolving to typed query result
 *
 * @example
 * ```typescript
 * interface ItemsQueryResult {
 *   items: Item[];
 *   itemsCount: number;
 * }
 *
 * const result = await executeGraphQLQuery<ItemsQueryResult>(
 *   ITEMS_QUERY,
 *   { skip: 0, limit: 10 }
 * );
 * console.log(result.items); // Typed as Item[]
 * ```
 */
export async function executeGraphQLQuery<TData = unknown>(
  query: string,
  variables?: Variables
): Promise<TData> {
  return graphqlClient.request<TData>(query, variables);
}
