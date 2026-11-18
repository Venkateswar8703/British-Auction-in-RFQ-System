import React from 'react';
import { RFQ, Bid } from '../../types';
import { StatusChip, RankBadge } from '../common/Primitives';
import { MapPin, ArrowRight, Shield, Info } from 'lucide-react';
import { format } from 'date-fns';

interface ShipmentSpecsPanelProps {
  rfq: RFQ;
  myLatestBid?: Bid | null;
  isSupplier: boolean;
}

export const ShipmentSpecsPanel: React.FC<ShipmentSpecsPanelProps> = ({
  rfq,
  myLatestBid,
  isSupplier,
}) => {
  return (
    <div className="flex flex-col gap-5 h-full text-meridian-ink">
      {/* Shipment Specs Header Box */}
      <div className="bg-meridian-surface border border-meridian-line p-5">
        <div className="flex items-center justify-between pb-3 border-b border-meridian-line">
          <div>
            <div className="text-[11px] font-mono text-meridian-muted uppercase tracking-[0.08em]">
              RFQ Reference ID
            </div>
            <div className="font-mono text-base font-bold text-meridian-ink tracking-wide">
              {rfq.reference_id}
            </div>
          </div>
          <StatusChip status={rfq.status} size="sm" />
        </div>

        <div className="mt-4">
          <h2 className="font-heading text-lg font-medium text-meridian-ink leading-tight">
            {rfq.title}
          </h2>
          {rfq.description && (
            <p className="mt-2 text-xs text-meridian-muted leading-relaxed">
              {rfq.description}
            </p>
          )}
        </div>

        {/* Origin to Destination Corridor */}
        <div className="mt-4 p-3 bg-meridian-surfaceDeep border border-meridian-line">
          <div className="text-[11px] font-mono uppercase text-meridian-muted tracking-[0.08em] mb-2">
            Routing Corridor
          </div>
          <div className="flex items-center justify-between text-xs font-mono font-medium">
            <div className="flex items-center gap-1.5 text-meridian-ink">
              <MapPin className="w-3.5 h-3.5 text-meridian-ink shrink-0" />
              <span className="truncate max-w-[120px]">{rfq.origin}</span>
            </div>
            <ArrowRight className="w-4 h-4 text-meridian-muted shrink-0 mx-1" />
            <div className="flex items-center gap-1.5 text-meridian-ink">
              <MapPin className="w-3.5 h-3.5 text-meridian-orange shrink-0" />
              <span className="truncate max-w-[120px]">{rfq.destination}</span>
            </div>
          </div>
        </div>

        {/* Milestone Dates Grid */}
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="p-3 bg-meridian-surfaceDeep border border-meridian-line">
            <div className="text-[10px] text-meridian-muted uppercase tracking-wider">Pickup Date</div>
            <div className="mt-1 font-semibold text-meridian-ink">
              {format(new Date(rfq.pickup_date), 'MMM dd, yyyy')}
            </div>
          </div>
          <div className="p-3 bg-meridian-surfaceDeep border border-meridian-line">
            <div className="text-[10px] text-meridian-muted uppercase tracking-wider">Start Time</div>
            <div className="mt-1 font-semibold text-meridian-ink">
              {format(new Date(rfq.bid_start), 'HH:mm:ss')} UTC
            </div>
          </div>
        </div>

        {/* British Auction Timing Configuration */}
        {rfq.config && (
          <div className="mt-4 p-3 bg-meridian-surface border border-meridian-line text-xs font-mono">
            <div className="text-[11px] text-meridian-muted uppercase tracking-[0.08em] mb-2 flex items-center justify-between">
              <span>Trigger Criteria</span>
              <span className="font-bold text-meridian-ink bg-meridian-surfaceDeep px-1.5 py-0.5 border border-meridian-line">
                {rfq.config.trigger_type}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
              <div>
                <span className="text-meridian-muted">Window (X):</span>{' '}
                <span className="text-meridian-ink font-bold tabular-nums">{rfq.config.trigger_window_minutes}m</span>
              </div>
              <div>
                <span className="text-meridian-muted">Extension (Y):</span>{' '}
                <span className="text-meridian-ink font-bold tabular-nums">{rfq.config.extension_minutes}m</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Supplier's Active Submitted Quote Details */}
      {isSupplier && (
        <div className="bg-meridian-surface border border-meridian-line p-5 flex-1">
          <div className="flex items-center justify-between pb-3 border-b border-meridian-line">
            <div className="text-xs font-mono font-bold uppercase text-meridian-ink tracking-wide flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-meridian-ink" />
              Your Active Standing Quote
            </div>
            {myLatestBid && (
              <span className="text-[10px] font-mono text-meridian-ink bg-meridian-lime px-2 py-0.5 border border-meridian-ink font-semibold">
                CONFIRMED
              </span>
            )}
          </div>

          {myLatestBid ? (
            <div className="mt-4 space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between p-3 bg-meridian-surfaceDeep border border-meridian-line">
                <span className="text-meridian-muted text-[11px] uppercase tracking-wider">Your Rank</span>
                <div className="flex items-center gap-2">
                  <RankBadge rank={myLatestBid.rank || 1} />
                  <span className="font-bold text-base text-meridian-ink">
                    {myLatestBid.rank === 1 ? 'Leading (L1)' : `L${myLatestBid.rank}`}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <div className="p-2.5 bg-meridian-surfaceDeep border border-meridian-line">
                  <span className="text-meridian-muted text-[9px] uppercase tracking-wider block">Freight</span>
                  <span className="font-bold text-meridian-ink tabular-nums">${Number(myLatestBid.freight_charges).toFixed(2)}</span>
                </div>
                <div className="p-2.5 bg-meridian-surfaceDeep border border-meridian-line">
                  <span className="text-meridian-muted text-[9px] uppercase tracking-wider block">Origin</span>
                  <span className="font-bold text-meridian-ink tabular-nums">${Number(myLatestBid.origin_charges).toFixed(2)}</span>
                </div>
                <div className="p-2.5 bg-meridian-surfaceDeep border border-meridian-line">
                  <span className="text-meridian-muted text-[9px] uppercase tracking-wider block">Dest.</span>
                  <span className="font-bold text-meridian-ink tabular-nums">${Number(myLatestBid.destination_charges).toFixed(2)}</span>
                </div>
              </div>

              <div className="flex items-center justify-between p-3 bg-meridian-surface border-2 border-meridian-ink font-bold text-sm">
                <span className="text-meridian-muted text-xs uppercase tracking-wider">Total Rate</span>
                <span className="text-meridian-ink text-base tabular-nums">
                  ${Number(myLatestBid.total).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
              </div>

              <div className="pt-2 text-[11px] text-meridian-muted space-y-1.5 border-t border-meridian-line">
                <div className="flex justify-between">
                  <span>Carrier:</span>
                  <span className="text-meridian-ink font-semibold">{myLatestBid.carrier_name}</span>
                </div>
                <div className="flex justify-between">
                  <span>Transit:</span>
                  <span className="text-meridian-ink font-semibold tabular-nums">{myLatestBid.transit_time_days} Days</span>
                </div>
                <div className="flex justify-between">
                  <span>Valid Until:</span>
                  <span className="text-meridian-ink font-semibold">{format(new Date(myLatestBid.quote_validity_date), 'MMM dd, yyyy')}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-meridian-muted text-xs font-mono">
              <Info className="w-5 h-5 mx-auto text-meridian-muted mb-2" />
              No quote submitted yet on this auction.
              <p className="text-[11px] text-meridian-ink font-medium mt-1">Submit your initial quote in the center panel.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
