/**
 * Shared API contract — types used by both frontend and backend.
 *
 * Add interfaces here when a shape is consumed on both sides of the wire.
 * Keep this file free of runtime code; types only.
 */

// ---------------------------------------------------------------------------
// Common primitives
// ---------------------------------------------------------------------------

/** ISO 8601 date-time string, e.g. "2024-01-15T10:30:00Z" */
export type ISODateString = string;

/** Opaque branded ID to prevent mixing up entity IDs at the type level. */
export type Brand<T, B extends string> = T & { readonly __brand: B };

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
}

// ---------------------------------------------------------------------------
// Error envelope
// ---------------------------------------------------------------------------

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: ApiError;
}

// ---------------------------------------------------------------------------
// TODO: Project-specific types
// ---------------------------------------------------------------------------
// Add your domain entity types here. Examples:
//
// export type UserId = Brand<string, "UserId">;
//
// export interface User {
//   id: UserId;
//   email: string;
//   createdAt: ISODateString;
// }
//
// export interface CreateUserRequest {
//   email: string;
//   name: string;
// }
