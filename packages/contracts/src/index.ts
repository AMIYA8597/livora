export * from './auth';
export * from './profile';
export * from './property';
export * from './matching';
export * from './group';
export * from './application';
export * from './messaging';
export * from './verification';
export * from './operations';

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  meta?: {
    page?: number;
    limit?: number;
    total?: number;
  };
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown[];
  };
}
