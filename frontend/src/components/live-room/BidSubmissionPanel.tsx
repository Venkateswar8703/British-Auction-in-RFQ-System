import React, { useState, useEffect } from 'react';
import { RFQ, Bid } from '../../types';
import { api, ApiError } from '../../services/api';
import { ArrowDownRight, ShieldAlert, Send, Sparkles, CheckCircle, AlertCircle } from 'lucide-react';
import { addDays, format } from 'date-fns';

interface BidSubmissionPanelProps {
  rfq: RFQ;
  currentLowestBid: number | null;
  myLatestBid?: Bid | null;
  isBuyer: boolean;
  onBidSuccess: (bid: Bid) => void;
}

export const BidSubmissionPanel: React.FC<BidSubmissionPanelProps> = ({
  rfq,
  currentLowestBid,
  myLatestBid,
  isBuyer,
  onBidSuccess,
}) => {
  const [freight, setFreight] = useState<string>('2100');
  const [origin, setOrigin] = useState<string>('150');
  const [destination, setDestination] = useState<string>('200');
  const [transitDays, setTransitDays] = useState<string>('14');
  const [carrierName, setCarrierName] = useState<string>('Commercial Direct Liner');
  const [validityDate, setValidityDate] = useState<string>(
    format(addDays(new Date(rfq.pickup_date || new Date()), 15), 'yyyy-MM-dd')
  );

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [skipConfirmation, setSkipConfirmation] = useState<boolean>(false);

  // Listen for Escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showConfirmModal) {
        setShowConfirmModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showConfirmModal]);

  // Live total calculation
  const numFreight = parseFloat(freight) || 0;
  const numOrigin = parseFloat(origin) || 0;
  const numDest = parseFloat(destination) || 0;
  const total = numFreight + numOrigin + numDest;

  const previousTotal = myLatestBid ? Number(myLatestBid.total) : null;
  const isLowerThanOwn = previousTotal === null || total < previousTotal;

  // Auto-set initial competitive numbers based on current lowest or standing
  useEffect(() => {
    if (currentLowestBid && currentLowestBid > 100 && (!myLatestBid || Number(myLatestBid.total) >= currentLowestBid)) {
      const target = currentLowestBid - 50;
      setFreight((target * 0.8).toFixed(2));
      setOrigin((target * 0.1).toFixed(2));
      setDestination((target * 0.1).toFixed(2));
    }
  }, [currentLowestBid]);

  const applyUnderbidPreset = (discount: number) => {
    const reference = myLatestBid && Number(myLatestBid.total) < (currentLowestBid || Infinity)
      ? Number(myLatestBid.total)
      : (currentLowestBid || 2500);

    const targetTotal = Math.max(100, reference - discount);
    const f = Math.round(targetTotal * 0.8);
    const o = Math.round(targetTotal * 0.1);
    const d = targetTotal - f - o;

    setFreight(f.toFixed(2));
    setOrigin(o.toFixed(2));
    setDestination(d.toFixed(2));
    setErrorMessage(null);
  };

  const handlePromptSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (numFreight <= 0 || numOrigin <= 0 || numDest <= 0) {
      setErrorMessage('Freight, Origin, and Destination charges must each be strictly greater than $0.');
      return;
    }

    if (previousTotal !== null && total >= previousTotal) {
      setErrorMessage(`New quote total ($${total.toFixed(2)}) must be strictly lower than your previous quote ($${previousTotal.toFixed(2)}).`);
      return;
    }

    if (skipConfirmation) {
      executeSubmit();
    } else {
      setShowConfirmModal(true);
    }
  };

  const executeSubmit = async () => {
    setIsSubmitting(true);
    setShowConfirmModal(false);
    const idempotencyKey = `bid-${rfq.id.slice(0, 8)}-${Date.now()}`;

    try {
      const result = await api.submitBid(
        rfq.id,
        {
          freight_charges: numFreight,
          origin_charges: numOrigin,
          destination_charges: numDest,
          transit_time_days: parseInt(transitDays, 10) || 14,
          quote_validity_date: new Date(validityDate).toISOString(),
          carrier_name: carrierName.trim() || 'Express Line',
        },
        idempotencyKey
      );

      setSuccessMessage(`Quote submitted! Total: $${Number(result.total).toFixed(2)} (Rank: L${result.rank || 1})`);
      onBidSuccess(result);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(`[${err.code}] ${err.message}`);
      } else {
        setErrorMessage(err.message || 'An error occurred submitting the quote.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isBuyer) {
    return (
      <div className="bg-meridian-surface border border-meridian-line p-5">
        <div className="p-4 bg-meridian-surfaceDeep border border-meridian-line text-center">
          <div className="text-xs font-mono font-bold text-meridian-ink uppercase tracking-wider flex items-center justify-center gap-2">
            <Sparkles className="w-4 h-4 text-meridian-ink" />
            Buyer Observation Console
          </div>
          <p className="mt-1.5 text-xs text-meridian-muted max-w-md mx-auto leading-relaxed">
            You are viewing this Live Auction Room as a Buyer. Bids are submitted directly by invited ocean carriers in real time.
          </p>
        </div>
      </div>
    );
  }

  if (rfq.status === 'CLOSED' || rfq.status === 'FORCE_CLOSED') {
    return (
      <div className="bg-meridian-surface border border-meridian-line p-5 text-center">
        <div className="text-xs font-mono font-bold text-meridian-orange uppercase tracking-wider">
          Bidding Concluded
        </div>
        <p className="mt-1 text-xs text-meridian-muted font-mono">
          This auction has reached its effective close. No further bids can be accepted.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-meridian-surface border border-meridian-line p-5 text-meridian-ink">
      <div className="flex items-center justify-between pb-3 border-b border-meridian-line mb-4">
        <div className="text-xs font-mono font-bold uppercase text-meridian-ink tracking-wider flex items-center gap-2">
          <Send className="w-3.5 h-3.5 text-meridian-ink" />
          Submit Competitive Quote
        </div>
        {previousTotal !== null && (
          <div className="text-[11px] font-mono text-meridian-muted">
            Prior Best: <span className="text-meridian-ink font-bold tabular-nums">${previousTotal.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* Quick Action Presets */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-[11px] font-mono text-meridian-muted uppercase tracking-wider">Presets:</span>
        <button
          type="button"
          onClick={() => applyUnderbidPreset(25)}
          className="btn-secondary px-2.5 py-1 text-[11px] font-mono flex items-center gap-1"
        >
          <ArrowDownRight className="w-3 h-3" />
          -$25 Underbid
        </button>
        <button
          type="button"
          onClick={() => applyUnderbidPreset(50)}
          className="btn-secondary px-2.5 py-1 text-[11px] font-mono flex items-center gap-1"
        >
          <ArrowDownRight className="w-3 h-3" />
          -$50 Underbid
        </button>
        <button
          type="button"
          onClick={() => applyUnderbidPreset(100)}
          className="btn-secondary px-2.5 py-1 text-[11px] font-mono flex items-center gap-1"
        >
          <ArrowDownRight className="w-3 h-3" />
          -$100 Underbid
        </button>
      </div>

      {rfq.config?.min_decrement && Number(rfq.config.min_decrement) > 0 && (
        <div className="text-[11px] font-mono text-meridian-ink bg-meridian-surfaceDeep border border-meridian-line px-3 py-1.5 mb-3 flex items-center justify-between">
          <span className="text-meridian-muted uppercase tracking-wider">Required Min Decrement:</span>
          <span className="font-bold tabular-nums text-meridian-ink">${Number(rfq.config.min_decrement).toFixed(2)}</span>
        </div>
      )}

      <form onSubmit={handlePromptSubmit} className="space-y-4 font-mono text-xs">
        {/* Cost breakdown inputs */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-meridian-muted uppercase tracking-wider block mb-1">
              Freight ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="1"
              value={freight}
              onChange={(e) => setFreight(e.target.value)}
              className="w-full bg-meridian-surface border border-meridian-line px-3 py-2 text-meridian-ink font-bold focus:border-meridian-ink outline-none"
              required
            />
          </div>
          <div>
            <label className="text-[10px] text-meridian-muted uppercase tracking-wider block mb-1">
              Origin ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="1"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              className="w-full bg-meridian-surface border border-meridian-line px-3 py-2 text-meridian-ink font-bold focus:border-meridian-ink outline-none"
              required
            />
          </div>
          <div>
            <label className="text-[10px] text-meridian-muted uppercase tracking-wider block mb-1">
              Dest ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="1"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              className="w-full bg-meridian-surface border border-meridian-line px-3 py-2 text-meridian-ink font-bold focus:border-meridian-ink outline-none"
              required
            />
          </div>
        </div>

        {/* Operating Carrier & Transit Days */}
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="text-[10px] text-meridian-muted uppercase tracking-wider block mb-1">
              Operating Carrier Name
            </label>
            <input
              type="text"
              value={carrierName}
              onChange={(e) => setCarrierName(e.target.value)}
              className="w-full bg-meridian-surface border border-meridian-line px-3 py-2 text-meridian-ink font-medium focus:border-meridian-ink outline-none text-xs"
              required
            />
          </div>
          <div>
            <label className="text-[10px] text-meridian-muted uppercase tracking-wider block mb-1">
              Transit (Days)
            </label>
            <input
              type="number"
              min="1"
              value={transitDays}
              onChange={(e) => setTransitDays(e.target.value)}
              className="w-full bg-meridian-surface border border-meridian-line px-3 py-2 text-meridian-ink font-bold focus:border-meridian-ink outline-none"
              required
            />
          </div>
        </div>

        {/* Live Total Calculation Preview Box */}
        <div className={`p-3.5 border flex items-center justify-between ${
          !isLowerThanOwn 
            ? 'bg-meridian-orange text-meridian-ink border-meridian-ink' 
            : 'bg-meridian-surfaceDeep border-meridian-line text-meridian-ink'
        }`}>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-meridian-muted">
              Calculated Total Rate
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-meridian-ink">
              ${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          {!isLowerThanOwn ? (
            <div className="text-right text-xs font-mono font-semibold flex items-center gap-1.5 text-meridian-ink">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>Must beat ${previousTotal?.toFixed(2)}</span>
            </div>
          ) : (
            <div className="text-right text-xs font-mono font-semibold text-meridian-ink">
              Valid Lower Quote
            </div>
          )}
        </div>

        {/* Feedback Alerts */}
        {errorMessage && (
          <div role="alert" aria-live="assertive" className="p-3 bg-meridian-orange text-meridian-ink border border-meridian-ink text-xs font-mono flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div role="status" aria-live="polite" className="p-3 bg-meridian-lime text-meridian-ink border border-meridian-ink text-xs font-mono font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting || !isLowerThanOwn}
          className="btn-primary w-full py-3 font-mono uppercase tracking-wider font-bold text-xs flex items-center justify-center gap-2"
        >
          {isSubmitting ? 'Transacting on Ledger...' : 'Submit Authoritative Bid'}
        </button>
      </form>

      {/* Improvement #4: Pre-bid Confirmation Guardrail Modal */}
      {showConfirmModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-[2px]"
          onClick={() => setShowConfirmModal(false)}
        >
          <div 
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-modal-title"
            onClick={(e) => e.stopPropagation()}
            className="bg-meridian-surface border-2 border-meridian-ink shadow-float max-w-md w-full p-6 text-meridian-ink animate-in fade-in zoom-in-95 duration-150"
          >
            <div id="confirm-modal-title" className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-meridian-orange pb-3 border-b border-meridian-line mb-4">
              <ShieldAlert className="w-4 h-4 text-meridian-orange" />
              Pre-Bid Confirmation Guardrail
            </div>

            <div className="space-y-4 font-mono text-xs">
              <p className="text-meridian-muted leading-relaxed">
                Review your authoritative freight quote before committing to the MERIDIAN British Auction ledger.
              </p>

              {/* Rate Breakdown Card */}
              <div className="p-3 bg-meridian-surfaceDeep border border-meridian-line space-y-2">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-meridian-muted">Ocean Freight:</span>
                  <span className="font-bold tabular-nums">${numFreight.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-meridian-muted">Origin Charges:</span>
                  <span className="font-bold tabular-nums">${numOrigin.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-meridian-muted">Destination Charges:</span>
                  <span className="font-bold tabular-nums">${numDest.toFixed(2)}</span>
                </div>
                <div className="pt-2 border-t border-meridian-line flex justify-between items-center text-sm font-bold">
                  <span>Total Bid Value:</span>
                  <span className="text-base text-meridian-ink tabular-nums">${total.toFixed(2)}</span>
                </div>
              </div>

              {/* Projected Rank & Impact */}
              <div className="p-3 border border-meridian-line bg-meridian-surface space-y-1.5">
                <div className="text-[10px] uppercase tracking-wider text-meridian-muted">
                  Projected Auction Standing
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold">
                    {currentLowestBid === null || total < currentLowestBid
                      ? '🏆 New Lowest Bid (L1 Leader)'
                      : `Trailing L1 by $${(total - currentLowestBid).toFixed(2)}`}
                  </span>
                  {previousTotal !== null && (
                    <span className="text-[11px] text-meridian-muted">
                      Reduction: -${(previousTotal - total).toFixed(2)}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-meridian-muted">
                  Carrier: <span className="font-semibold text-meridian-ink">{carrierName}</span> · {transitDays} transit days
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="skip-check"
                  checked={skipConfirmation}
                  onChange={(e) => setSkipConfirmation(e.target.checked)}
                  className="rounded border-meridian-line text-meridian-ink focus:ring-0"
                />
                <label htmlFor="skip-check" className="text-[11px] text-meridian-muted cursor-pointer select-none">
                  Skip confirmation for rapid bidding in this session
                </label>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConfirmModal(false)}
                  className="btn-secondary flex-1 py-2 font-mono uppercase text-xs"
                >
                  Back & Revise
                </button>
                <button
                  type="button"
                  onClick={executeSubmit}
                  disabled={isSubmitting}
                  className="btn-primary flex-1 py-2 font-mono uppercase font-bold text-xs flex items-center justify-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  Confirm & Submit
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
