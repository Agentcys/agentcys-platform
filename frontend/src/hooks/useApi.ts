import { useMemo } from 'react';
import { apiClient } from '../api/client';

export function useApi() {
  return useMemo(() => apiClient, []);
}
