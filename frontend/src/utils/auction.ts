/**
 * Core utility functions for MERIDIAN auction client-side logic
 * Mirrors the authoritative backend rules for optimistic validation and UI display.
 */

export interface BidFormValues {
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  transit_time_days: number;
  carrier_name: string;
  quote_validity_date: string;
}

export interface BidItem {
  id: string;
  supplier_id: string;
  supplier_name: string;
  total: number;
  created_at: string;
  is_leading?: boolean;
}

/**
 * Computes total freight rate from components
 */
export function calculateBidTotal(
  freight: number,
  origin: number,
  destination: number
): number {
  const f = isNaN(freight) ? 0 : Number(freight);
  const o = isNaN(origin) ? 0 : Number(origin);
  const d = isNaN(destination) ? 0 : Number(destination);
  return Math.round((f + o + d) * 100) / 100;
}

/**
 * Validates bid fields against British Auction rules
 */
export function validateBidSubmission(
  values: BidFormValues,
  previousBestTotal: number | null,
  effectiveCloseDate: string,
  nowServerTime: number = Date.now()
): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (values.freight_charges <= 0) {
    errors.push('Freight charges must be greater than 0');
  }
  if (values.origin_charges <= 0) {
    errors.push('Origin charges must be greater than 0');
  }
  if (values.destination_charges <= 0) {
    errors.push('Destination charges must be greater than 0');
  }
  if (values.transit_time_days <= 0) {
    errors.push('Transit time must be at least 1 day');
  }
  if (!values.carrier_name || values.carrier_name.trim().length === 0) {
    errors.push('Carrier name is required');
  }

  const total = calculateBidTotal(
    values.freight_charges,
    values.origin_charges,
    values.destination_charges
  );

  // British Auction rule: New bid must be strictly lower than supplier's previous best
  if (previousBestTotal !== null && total >= previousBestTotal) {
    errors.push(
      `Bid total ($${total.toLocaleString()}) must be strictly lower than your previous quote ($${previousBestTotal.toLocaleString()})`
    );
  }

  // Time check
  const closeTime = new Date(effectiveCloseDate).getTime();
  if (nowServerTime >= closeTime) {
    errors.push('Auction has closed. Submissions are rejected.');
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

/**
 * Checks if a bid time falls inside the trigger window [effective_close - X, effective_close)
 */
export function isInsideTriggerWindow(
  bidTimestamp: number,
  effectiveCloseTimestamp: number,
  triggerWindowMinutes: number
): boolean {
  const triggerWindowMs = triggerWindowMinutes * 60 * 1000;
  const windowStart = effectiveCloseTimestamp - triggerWindowMs;
  return bidTimestamp >= windowStart && bidTimestamp < effectiveCloseTimestamp;
}

/**
 * Computes network clock drift: drift = serverTime - clientReceiveTime
 */
export function calculateClockDrift(
  serverTimeIso: string,
  clientReceiveTimeMs: number = Date.now()
): number {
  const serverMs = new Date(serverTimeIso).getTime();
  return serverMs - clientReceiveTimeMs;
}

/**
 * Formats milliseconds into high-precision HH:MM:SS or MM:SS
 */
export function formatTimeRemaining(ms: number): {
  hours: string;
  minutes: string;
  seconds: string;
  millis: string;
  isUrgent: boolean;
  isExpired: boolean;
} {
  if (ms <= 0) {
    return {
      hours: '00',
      minutes: '00',
      seconds: '00',
      millis: '00',
      isUrgent: false,
      isExpired: true,
    };
  }

  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const tenths = Math.floor((ms % 1000) / 10);

  return {
    hours: hours.toString().padStart(2, '0'),
    minutes: minutes.toString().padStart(2, '0'),
    seconds: seconds.toString().padStart(2, '0'),
    millis: tenths.toString().padStart(2, '0'),
    isUrgent: ms < 5 * 60 * 1000, // < 5 minutes
    isExpired: false,
  };
}

/**
 * Sorts and ranks unique suppliers by their latest valid bid.
 * Ranking is by total ascending (L1 lowest).
 * Ties are broken by earlier created_at timestamp.
 */
export function rankBids<T extends BidItem>(bids: T[]): (T & { rank: number })[] {
  // 1. Group by supplier and pick latest bid
  const supplierLatestMap = new Map<string, T>();
  for (const bid of bids) {
    const existing = supplierLatestMap.get(bid.supplier_id);
    if (!existing || new Date(bid.created_at) > new Date(existing.created_at)) {
      supplierLatestMap.set(bid.supplier_id, bid);
    }
  }

  // 2. Sort by total ascending, then created_at ascending (earlier bid wins tie)
  const uniqueBids = Array.from(supplierLatestMap.values());
  uniqueBids.sort((a, b) => {
    if (a.total !== b.total) {
      return a.total - b.total;
    }
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });

  // 3. Assign 1-based ranks
  return uniqueBids.map((b, index) => ({
    ...b,
    rank: index + 1,
  }));
}

/**
 * Extracts UN/LOCODE from port strings (e.g. "PSA Singapore (SGSIN)" -> "SGSIN")
 */
export function extractLocode(portStr: string): string {
  if (!portStr) return '—';
  const match = portStr.match(/\(([A-Z0-9]{5})\)/);
  if (match) return match[1];
  const words = portStr.replace(/[^A-Za-z0-9 ]/g, '').trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0].slice(0, 2) + words[1].slice(0, 3)).toUpperCase();
  }
  return portStr.slice(0, 5).toUpperCase();
}

/**
 * Formats date into date/time line ("17 Nov, 19:11") and timezone abbreviation ("IST" or "UTC").
 * Only shows the year if it differs from the current year.
 */
export function formatAuctionDateParts(dateStr: string, isUtc: boolean): {
  datePart: string;
  tzPart: string;
} {
  if (!dateStr) return { datePart: '—', tzPart: '' };
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return { datePart: '—', tzPart: '' };

  const currentYear = isUtc ? new Date().getUTCFullYear() : new Date().getFullYear();
  const year = isUtc ? d.getUTCFullYear() : d.getFullYear();
  const showYear = year !== currentYear;

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const day = isUtc ? d.getUTCDate() : d.getDate();
  const month = months[isUtc ? d.getUTCMonth() : d.getMonth()];
  const pad = (n: number) => n.toString().padStart(2, '0');
  const hours = pad(isUtc ? d.getUTCHours() : d.getHours());
  const minutes = pad(isUtc ? d.getUTCMinutes() : d.getMinutes());

  const yearStr = showYear ? ` ${year}` : '';
  const datePart = `${day} ${month}${yearStr}, ${hours}:${minutes}`;

  let tzPart = 'UTC';
  if (!isUtc) {
    try {
      const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' }).formatToParts(d);
      const tzMatch = parts.find((p) => p.type === 'timeZoneName');
      tzPart = tzMatch ? tzMatch.value : '';
    } catch {
      tzPart = '';
    }
  }

  return { datePart, tzPart };
}

/**
 * Formats date either in User Local Timezone with abbreviation or UTC
 */
export function formatDateDisplay(dateStr: string, isUtc: boolean): string {
  if (!dateStr) return '—';
  const parts = formatAuctionDateParts(dateStr, isUtc);
  return `${parts.datePart} ${parts.tzPart}`.trim();
}

