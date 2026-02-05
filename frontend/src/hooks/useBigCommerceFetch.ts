import { useCallback } from 'react';

/**
 * Hook for making authenticated requests to the backend API.
 * Uses store_hash query parameter for authentication.
 */
export function useBigCommerceFetch() {
  // Get store_hash from URL
  const getStoreHash = useCallback((): string | null => {
    const params = new URLSearchParams(window.location.search);
    return params.get('store_hash');
  }, []);

  const fetchWithAuth = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      const storeHash = getStoreHash();

      if (!storeHash) {
        throw new Error('Store hash not found in URL');
      }

      // Add store_hash to URL
      const separator = url.includes('?') ? '&' : '?';
      const apiUrl = `${url}${separator}store_hash=${storeHash}`;

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string>),
      };

      return fetch(apiUrl, {
        ...options,
        headers,
      });
    },
    [getStoreHash]
  );

  const get = useCallback(
    async <T>(url: string): Promise<T> => {
      const response = await fetchWithAuth(url);
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Request failed');
      }
      return response.json();
    },
    [fetchWithAuth]
  );

  const post = useCallback(
    async <T>(url: string, data?: unknown): Promise<T> => {
      const response = await fetchWithAuth(url, {
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Request failed');
      }
      return response.json();
    },
    [fetchWithAuth]
  );

  const put = useCallback(
    async <T>(url: string, data?: unknown): Promise<T> => {
      const response = await fetchWithAuth(url, {
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Request failed');
      }
      return response.json();
    },
    [fetchWithAuth]
  );

  const del = useCallback(
    async <T>(url: string): Promise<T> => {
      const response = await fetchWithAuth(url, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Request failed');
      }
      return response.json();
    },
    [fetchWithAuth]
  );

  return { fetch: fetchWithAuth, get, post, put, del, getStoreHash };
}

// Type definitions for API responses
export interface StoreInfo {
  store_hash: string;
  store_name: string | null;
  store_domain: string | null;
  is_active: boolean;
  installed_at: string | null;
  brand_id: string | null;
  is_connected: boolean;
  settings: {
    auto_sync_products: boolean;
    cookie_duration_days: number;
    attribution_model: string;
  };
}

export interface Product {
  id: string;
  bc_product_id: number;
  title: string;
  handle: string | null;
  price: number | null;
  image_url: string | null;
  is_synced: boolean;
  last_synced_at: string | null;
}

export interface ProductsResponse {
  products: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface AnalyticsOverview {
  conversions: number;
  revenue: number;
  clicks: number;
  top_affiliates: Array<{
    id: string;
    name: string;
    conversions: number;
    revenue: number;
  }>;
  top_products: Array<{
    id: string;
    title: string;
    conversions: number;
    revenue: number;
  }>;
}
