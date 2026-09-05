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
// MCU Selector — used by web/ and miniprogram/
// ---------------------------------------------------------------------------

export type UnknownPolicy = "allow_risk" | "exclude";
export type Application = "motor_control" | "power_conversion" | "bms" | "industrial_control" | "iot";
export type NumericBound = { min?: number; max?: number };
export type Constraint = number | boolean | string | string[] | NumericBound;

export interface RecommendRequest {
  must?: Record<string, Constraint>;
  prefer?: Record<string, Constraint>;
  application?: Application | null;
  unknown_policy?: UnknownPolicy;
  limit?: number;
  include_inactive?: boolean;
}

export interface CompareRequest {
  manufacturer: string;
  part_number: string;
  source_note: string;
  specs: Record<string, number | boolean | string | string[]>;
  essential?: string[];
  weights?: Record<string, number>;
  limit?: number;
  include_inactive?: boolean;
}

export interface RecommendationItem {
  part_number: string;
  score: number;
  status?: string;
  facts?: Record<string, string | number>;
  matches?: string[];
  risks?: string[];
  comparisons?: string[];
}

export interface RecommendResponse {
  mode?: string;
  recommendations: RecommendationItem[];
  rejected_by_hard_constraints?: number;
  disclaimer?: string;
}

export interface InspectResponse {
  found: boolean;
  part_number: string;
  suggestions?: string[];
  normalized?: Record<string, string | number>;
  rpn?: {
    marketingStatus?: string;
    description?: string;
  };
  reference?: string;
}
