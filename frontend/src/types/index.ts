export type UserRole = 'buyer' | 'supplier';

export type RFQStatus = 'SCHEDULED' | 'ACTIVE' | 'CLOSED' | 'FORCE_CLOSED';

export type TriggerType = 'BID_RECEIVED' | 'ANY_RANK_CHANGE' | 'L1_CHANGE';

export interface SupplierSimple {
  id: string;
  name: string;
  code: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  supplier_id?: string | null;
  supplier?: SupplierSimple | null;
  created_at: string;
}

export interface Supplier {
  id: string;
  name: string;
  code: string;
  contact_email: string;
  contact_phone?: string;
  is_active: boolean;
  created_at: string;
}

export interface AuctionConfig {
  id: string;
  rfq_id: string;
  trigger_window_minutes: number;
  extension_minutes: number;
  trigger_type: TriggerType;
  created_at: string;
}

export interface RFQInvitation {
  id: string;
  supplier_id: string;
  supplier: SupplierSimple;
  status: string;
  created_at: string;
}

export interface Bid {
  id: string;
  rfq_id: string;
  supplier_id: string;
  supplier_name?: string;
  supplier_code?: string;
  submitted_by: string;
  submitter_name?: string;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  total: number;
  transit_time_days: number;
  quote_validity_date: string;
  carrier_name: string;
  idempotency_key?: string | null;
  created_at: string;
  rank?: number;
}

export interface SupplierRank {
  rank: number;
  supplier_id: string;
  supplier_name: string;
  supplier_code: string;
  total: number;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  transit_time_days: number;
  quote_validity_date: string;
  carrier_name: string;
  bid_id: string;
  bid_created_at: string;
  is_current_user_supplier: boolean;
}

export interface AuctionExtension {
  id: string;
  rfq_id: string;
  triggering_bid_id?: string | null;
  previous_close: string;
  new_close: string;
  trigger_type: string;
  reason: string;
  is_clamped: boolean;
  created_at: string;
}

export interface AuctionEvent {
  id: string;
  rfq_id: string;
  bid_id?: string | null;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
}

export interface RFQ {
  id: string;
  reference_id: string;
  title: string;
  description?: string;
  origin: string;
  destination: string;
  pickup_date: string;
  bid_start: string;
  bid_close: string;
  effective_close: string;
  forced_close: string;
  status: RFQStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  config?: AuctionConfig;
  invitations?: RFQInvitation[];
  lowest_bid_total?: number | null;
  total_bids_count: number;
  participating_suppliers_count: number;
  is_invited?: boolean;
  my_latest_bid?: Bid | null;
  my_rank?: number | null;
  server_time?: string;
  rankings?: SupplierRank[];
  recent_extensions?: AuctionExtension[];
  my_bid_history?: Bid[];
}

export interface WebSocketAuctionPayload {
  event_type: string;
  rfq_id: string;
  server_time: string;
  data: Record<string, any>;
}

export interface CommandCenterMetrics {
  summary: {
    total_rfqs: number;
    active_count: number;
    closed_count: number;
    force_closed_count: number;
    scheduled_count: number;
    total_bids: number;
    participating_suppliers: number;
    avg_price_reduction_pct: number;
  };
  upcoming_deadlines: Array<{
    id: string;
    reference_id: string;
    title: string;
    effective_close: string;
    forced_close: string;
    lowest_bid: number | null;
    bids_count: number;
  }>;
  recent_activity: Array<{
    id: string;
    rfq_id: string;
    rfq_ref: string;
    rfq_title: string;
    event_type: string;
    payload: Record<string, any>;
    created_at: string;
  }>;
  performance: Array<{
    rfq_ref: string;
    title: string;
    first_bid: number;
    current_l1: number;
    reduction_pct: number;
    bids_count: number;
  }>;
  server_time: string;
}

export interface SupplierPortalMetrics {
  summary: {
    total_invited: number;
    active_auctions_count: number;
    my_total_bids: number;
    l1_count: number;
    outbid_count: number;
  };
  active_auctions: Array<{
    id: string;
    reference_id: string;
    title: string;
    origin: string;
    destination: string;
    effective_close: string;
    forced_close: string;
    my_rank: number | null;
    my_bid: number | null;
    lowest_bid: number | null;
    total_bids: number;
  }>;
  recent_bids: Array<{
    bid_id: string;
    rfq_id: string;
    rfq_ref: string;
    rfq_title: string;
    total: number;
    transit_time_days: number;
    carrier_name: string;
    created_at: string;
  }>;
  server_time: string;
}

