import { describe, it, expect } from 'vitest';
import {
  calculateBidTotal,
  validateBidSubmission,
  isInsideTriggerWindow,
  calculateClockDrift,
  formatTimeRemaining,
  rankBids,
  extractLocode,
  formatDateDisplay,
  formatAuctionDateParts,
  BidItem,
} from '../utils/auction';

describe('MERIDIAN Client Auction Logic', () => {
  describe('calculateBidTotal', () => {
    it('accurately sums freight, origin, and destination charges', () => {
      const total = calculateBidTotal(2500, 350.5, 275.25);
      expect(total).toBe(3125.75);
    });

    it('handles zero or NaN gracefully', () => {
      expect(calculateBidTotal(0, 0, 0)).toBe(0);
      expect(calculateBidTotal(NaN as any, 100, 200)).toBe(300);
    });
  });

  describe('validateBidSubmission', () => {
    const validValues = {
      freight_charges: 2000,
      origin_charges: 300,
      destination_charges: 200,
      transit_time_days: 14,
      carrier_name: 'Maersk Line',
      quote_validity_date: '2026-12-01',
    };

    it('allows valid initial bid with no previous bid', () => {
      const futureClose = new Date(Date.now() + 3600 * 1000).toISOString();
      const result = validateBidSubmission(validValues, null, futureClose, Date.now());
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('allows strictly lower subsequent bid', () => {
      const futureClose = new Date(Date.now() + 3600 * 1000).toISOString();
      // Total is 2500. Previous was 2600.
      const result = validateBidSubmission(validValues, 2600, futureClose, Date.now());
      expect(result.isValid).toBe(true);
    });

    it('rejects subsequent bid equal to or higher than previous bid (British Auction rule)', () => {
      const futureClose = new Date(Date.now() + 3600 * 1000).toISOString();
      // Total is 2500. Previous was 2500 (equal)
      const resEqual = validateBidSubmission(validValues, 2500, futureClose, Date.now());
      expect(resEqual.isValid).toBe(false);
      expect(resEqual.errors[0]).toContain('strictly lower');

      // Total is 2500. Previous was 2400 (higher)
      const resHigher = validateBidSubmission(validValues, 2400, futureClose, Date.now());
      expect(resHigher.isValid).toBe(false);
      expect(resHigher.errors[0]).toContain('strictly lower');
    });

    it('rejects zero or negative charges', () => {
      const futureClose = new Date(Date.now() + 3600 * 1000).toISOString();
      const invalid = { ...validValues, freight_charges: 0, origin_charges: -50 };
      const res = validateBidSubmission(invalid, null, futureClose, Date.now());
      expect(res.isValid).toBe(false);
      expect(res.errors).toContain('Freight charges must be greater than 0');
      expect(res.errors).toContain('Origin charges must be greater than 0');
    });

    it('rejects bid when auction has passed effective close', () => {
      const pastClose = new Date(Date.now() - 5000).toISOString();
      const res = validateBidSubmission(validValues, null, pastClose, Date.now());
      expect(res.isValid).toBe(false);
      expect(res.errors).toContain('Auction has closed. Submissions are rejected.');
    });
  });

  describe('isInsideTriggerWindow', () => {
    const effectiveClose = new Date('2026-11-17T18:00:00Z').getTime();
    const triggerMinutes = 10; // window is 17:50:00 to 18:00:00

    it('returns true when bid is within the X-minute window', () => {
      const bidAt1755 = new Date('2026-11-17T17:55:00Z').getTime();
      expect(isInsideTriggerWindow(bidAt1755, effectiveClose, triggerMinutes)).toBe(true);

      const bidAtWindowEdge = new Date('2026-11-17T17:50:00Z').getTime();
      expect(isInsideTriggerWindow(bidAtWindowEdge, effectiveClose, triggerMinutes)).toBe(true);
    });

    it('returns false when bid is before the window', () => {
      const bidAt1745 = new Date('2026-11-17T17:45:00Z').getTime();
      expect(isInsideTriggerWindow(bidAt1745, effectiveClose, triggerMinutes)).toBe(false);
    });

    it('returns false when bid is at or after effective close', () => {
      const bidAt1800 = new Date('2026-11-17T18:00:00Z').getTime();
      expect(isInsideTriggerWindow(bidAt1800, effectiveClose, triggerMinutes)).toBe(false);
    });
  });

  describe('calculateClockDrift and formatTimeRemaining', () => {
    it('correctly calculates network drift between server and client', () => {
      const serverIso = '2026-11-17T12:00:01.000Z';
      const clientMs = new Date('2026-11-17T12:00:00.000Z').getTime();
      const drift = calculateClockDrift(serverIso, clientMs);
      expect(drift).toBe(1000); // Server is 1 second ahead
    });

    it('formats milliseconds into high precision HH:MM:SS:ms display', () => {
      const ms = (2 * 3600 + 15 * 60 + 42) * 1000 + 850;
      const formatted = formatTimeRemaining(ms);
      expect(formatted.hours).toBe('02');
      expect(formatted.minutes).toBe('15');
      expect(formatted.seconds).toBe('42');
      expect(formatted.millis).toBe('85');
      expect(formatted.isUrgent).toBe(false);
      expect(formatted.isExpired).toBe(false);
    });

    it('flags urgency when remaining time is less than 5 minutes', () => {
      const ms = 4 * 60 * 1000 + 30 * 1000;
      const formatted = formatTimeRemaining(ms);
      expect(formatted.isUrgent).toBe(true);
      expect(formatted.isExpired).toBe(false);
    });

    it('handles zero or negative time as expired', () => {
      const formatted = formatTimeRemaining(-500);
      expect(formatted.isExpired).toBe(true);
      expect(formatted.minutes).toBe('00');
      expect(formatted.seconds).toBe('00');
    });
  });

  describe('rankBids', () => {
    it('ranks suppliers by total price ascending (L1 lowest)', () => {
      const bids: BidItem[] = [
        { id: '1', supplier_id: 's1', supplier_name: 'Maersk', total: 3100, created_at: '2026-11-17T10:00:00Z' },
        { id: '2', supplier_id: 's2', supplier_name: 'Hapag', total: 2900, created_at: '2026-11-17T10:01:00Z' },
        { id: '3', supplier_id: 's3', supplier_name: 'MSC', total: 3400, created_at: '2026-11-17T10:02:00Z' },
      ];

      const ranked = rankBids(bids);
      expect(ranked).toHaveLength(3);
      expect(ranked[0].supplier_name).toBe('Hapag'); // L1 (2900)
      expect(ranked[0].rank).toBe(1);
      expect(ranked[1].supplier_name).toBe('Maersk'); // L2 (3100)
      expect(ranked[1].rank).toBe(2);
      expect(ranked[2].supplier_name).toBe('MSC'); // L3 (3400)
      expect(ranked[2].rank).toBe(3);
    });

    it('only considers latest valid bid per supplier', () => {
      const bids: BidItem[] = [
        { id: '1', supplier_id: 's1', supplier_name: 'Maersk', total: 3500, created_at: '2026-11-17T10:00:00Z' },
        { id: '2', supplier_id: 's2', supplier_name: 'Hapag', total: 3200, created_at: '2026-11-17T10:01:00Z' },
        { id: '3', supplier_id: 's1', supplier_name: 'Maersk', total: 2800, created_at: '2026-11-17T10:05:00Z' }, // Maersk underbids Hapag
      ];

      const ranked = rankBids(bids);
      expect(ranked).toHaveLength(2); // Only s1 and s2
      expect(ranked[0].supplier_name).toBe('Maersk'); // L1 (2800)
      expect(ranked[0].total).toBe(2800);
      expect(ranked[1].supplier_name).toBe('Hapag'); // L2 (3200)
    });

    it('breaks ties on total by earlier timestamp', () => {
      const bids: BidItem[] = [
        { id: '1', supplier_id: 's1', supplier_name: 'Maersk', total: 3000, created_at: '2026-11-17T10:05:00Z' },
        { id: '2', supplier_id: 's2', supplier_name: 'Hapag', total: 3000, created_at: '2026-11-17T10:02:00Z' }, // Earlier
      ];

      const ranked = rankBids(bids);
      expect(ranked[0].supplier_name).toBe('Hapag'); // Wins tie because 10:02 < 10:05
      expect(ranked[1].supplier_name).toBe('Maersk');
    });
  });

  describe('extractLocode and formatDateDisplay', () => {
    it('extracts UN/LOCODE correctly from port descriptions', () => {
      expect(extractLocode('Shanghai Port (CNSHA)')).toBe('CNSHA');
      expect(extractLocode('Port of Long Beach (USLGB)')).toBe('USLGB');
      expect(extractLocode('PSA Singapore (SGSIN)')).toBe('SGSIN');
      expect(extractLocode('Port of Melbourne (AUMEL)')).toBe('AUMEL');
    });

    it('formats date in UTC with explicit suffix', () => {
      const iso = '2026-11-17T18:00:00.000Z';
      const parts = formatAuctionDateParts(iso, true);
      expect(parts.datePart).toContain('17 Nov');
      expect(parts.datePart).toContain('18:00');
      expect(parts.tzPart).toBe('UTC');
    });
  });
});

