import { User, RFQ, Bid, Supplier, CommandCenterMetrics, SupplierPortalMetrics, AuctionEvent } from '../types';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  code: string;
  details?: Record<string, any>;
  statusCode: number;

  constructor(code: string, message: string, statusCode: number, details?: Record<string, any>) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('meridian_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData = { code: 'UNKNOWN_ERROR', message: `Request failed with status ${response.status}`, details: {} };
    try {
      const json = await response.json();
      errorData = {
        code: json.code || 'API_ERROR',
        message: json.message || response.statusText,
        details: json.details,
      };
    } catch {
      // ignore
    }
    throw new ApiError(errorData.code, errorData.message, response.status, errorData.details);
  }

  return response.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  getMe: () => request<User>('/auth/me'),

  // RFQs
  listRfqs: (params?: { search?: string; status?: string; sort_by?: string; order?: string }) => {
    const query = new URLSearchParams();
    if (params?.search) query.append('search', params.search);
    if (params?.status) query.append('status', params.status);
    if (params?.sort_by) query.append('sort_by', params.sort_by);
    if (params?.order) query.append('order', params.order);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return request<RFQ[]>(`/rfqs${qs}`);
  },

  getRfq: (id: string) => request<RFQ>(`/rfqs/${id}`),

  createRfq: (payload: any) =>
    request<RFQ>('/rfqs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateRfq: (id: string, payload: any) =>
    request<RFQ>(`/rfqs/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  getRfqEvents: (id: string) => request<AuctionEvent[]>(`/rfqs/${id}/events`),

  reseedDemoRfq: (id: string) =>
    request<{ success: boolean; message: string; effective_close: string; forced_close: string }>(`/rfqs/${id}/reseed-demo`, {
      method: 'POST',
    }),

  awardRfq: (id: string, payload: { winning_bid_id: string; award_reason: string; notes?: string }) =>
    request<{ success: boolean; message: string; awarded_bid_id: string; carrier_name: string; total: number; award_reason: string }>(`/rfqs/${id}/award`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getExportCsvUrl: (id: string) => `${API_BASE}/rfqs/${id}/export-csv`,

  // Bids
  submitBid: (rfqId: string, payload: {
    freight_charges: number;
    origin_charges: number;
    destination_charges: number;
    transit_time_days: number;
    quote_validity_date: string;
    carrier_name: string;
  }, idempotencyKey?: string) => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return request<Bid>(`/rfqs/${rfqId}/bids`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  },

  listBids: (rfqId: string) => request<Bid[]>(`/rfqs/${rfqId}/bids`),

  // Suppliers
  listSuppliers: () => request<Supplier[]>('/suppliers'),

  // Analytics
  getCommandCenter: () => request<CommandCenterMetrics>('/analytics/command-center'),
  getSupplierPortal: () => request<SupplierPortalMetrics>('/analytics/supplier-portal'),
};

