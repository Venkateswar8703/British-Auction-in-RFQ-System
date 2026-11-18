import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { SupplierPortalMetrics } from '../types';
import { useAuth } from '../context/AuthContext';
import { CountdownTimer } from '../components/common/CountdownTimer';
import { RankBadge, SectionHeader, HairlineTable } from '../components/common/Primitives';
import { 
  Radio, 
  ArrowRight, 
  RefreshCw,
  AlertTriangle
} from 'lucide-react';
import { format } from 'date-fns';

export const SupplierPortal: React.FC = () => {
  const { user } = useAuth();
  const [metrics, setMetrics] = useState<SupplierPortalMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      const data = await api.getSupplierPortal();
      setMetrics(data);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load supplier metrics.');
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="py-24 text-center font-mono text-sm text-meridian-muted flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-meridian-ink" />
        Connecting to Carrier Workspace...
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="p-8 bg-meridian-surface border border-meridian-line text-center font-mono">
        <AlertTriangle className="w-8 h-8 text-meridian-orange mx-auto mb-2" />
        <div className="text-base font-bold text-meridian-ink">{error || 'Data unavailable'}</div>
        <button
          onClick={fetchMetrics}
          className="btn-secondary mt-4 px-4 py-1.5 text-xs"
        >
          Retry
        </button>
      </div>
    );
  }

  const { summary, active_auctions, recent_bids } = metrics;

  return (
    <div className="space-y-12 pb-16 text-meridian-ink">
      
      {/* 1. Header with Technical Grid Background */}
      <div className="technical-grid p-6 -mx-4 sm:-mx-6 lg:-mx-8 border-b border-meridian-line">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted flex items-center gap-2 mb-2">
              <span>CARRIER WORKSPACE</span>
              <span>/</span>
              <span className="text-meridian-ink font-semibold">{user?.supplier?.name || 'Carrier Partner'}</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-heading font-medium tracking-tight text-meridian-ink">
              Supplier Bidding Portal
            </h1>
            <p className="text-sm text-meridian-muted mt-1 leading-relaxed">
              Review invited freight auctions, track your standing ladder rank in real time, and counter rival quotes.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/live/demo"
              className="btn-primary px-4 py-2 font-mono text-xs uppercase tracking-wider flex items-center gap-2"
            >
              <Radio className="w-3.5 h-3.5" />
              Live Demo Room
            </Link>
            <button
              onClick={fetchMetrics}
              className="btn-secondary p-2"
              title="Refresh portal"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Editorial Numerals on Ivory Separated by Hairlines */}
      <div className="grid grid-cols-2 lg:grid-cols-4 border-y border-meridian-line divide-x divide-meridian-line py-6">
        
        <div className="px-4 sm:px-6 py-2">
          <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
            01 / Invited Auctions
          </span>
          <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums">
            {summary.total_invited}
          </div>
          <p className="mt-2 text-xs font-mono text-meridian-muted">
            Verified procurement RFQs
          </p>
        </div>

        <div className="px-4 sm:px-6 py-2">
          <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
            02 / Open Trading Rooms
          </span>
          <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums">
            {summary.active_auctions_count}
          </div>
          <p className="mt-2 text-xs font-mono text-meridian-muted">
            Currently accepting lower bids
          </p>
        </div>

        <div className="px-4 sm:px-6 py-2">
          <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
            03 / Leading (L1) Ranks
          </span>
          <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums flex items-baseline gap-2">
            <span>{summary.l1_count}</span>
            <span className="text-xs font-bold text-meridian-ink bg-meridian-lime px-1.5 py-0.2 border border-meridian-ink">
              L1
            </span>
          </div>
          <p className="mt-2 text-xs font-mono text-meridian-muted">
            Lowest rate currently held
          </p>
        </div>

        <div className="px-4 sm:px-6 py-2">
          <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
            04 / Outbid (Action Req.)
          </span>
          <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums flex items-baseline gap-2">
            <span>{summary.outbid_count}</span>
            {summary.outbid_count > 0 && (
              <span className="text-xs font-bold text-meridian-ink bg-meridian-orange px-1.5 py-0.2 border border-meridian-ink">
                OUTBID
              </span>
            )}
          </div>
          <p className="mt-2 text-xs font-mono text-meridian-muted">
            Below current market leader
          </p>
        </div>

      </div>

      {/* 3. Active Auctions You Can Bid In */}
      <div>
        <SectionHeader
          railLabel="01 / OPEN ROOMS"
          title="Active Auctions Requiring Bids"
          description="Direct access to live British Auction rooms where your organization is invited."
        />

        {active_auctions.length === 0 ? (
          <div className="py-12 text-center text-meridian-muted font-mono text-xs border border-meridian-line bg-meridian-surface">
            No active auctions open for bidding at this time.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {active_auctions.map((auction) => {
              const isL1 = auction.my_rank === 1;
              const isOutbid = auction.my_rank !== null && auction.my_rank > 1;

              return (
                <div
                  key={auction.id}
                  className={`p-5 border transition-all flex flex-col justify-between ${
                    isL1
                      ? 'bg-meridian-surface border-meridian-ink'
                      : isOutbid
                      ? 'bg-meridian-surface border-meridian-line'
                      : 'bg-meridian-surface border-meridian-line'
                  }`}
                >
                  <div>
                    {/* Header: Reference & Rank Badge */}
                    <div className="flex items-center justify-between mb-3 pb-2 border-b border-meridian-line">
                      <span className="font-mono text-xs font-bold text-meridian-ink">
                        {auction.reference_id}
                      </span>
                      {auction.my_rank ? (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-mono text-meridian-muted uppercase">Your Rank:</span>
                          <RankBadge rank={auction.my_rank} isL1={isL1} />
                        </div>
                      ) : (
                        <span className="font-mono text-[10px] text-meridian-muted bg-meridian-surfaceDeep px-2 py-0.5 border border-meridian-line">
                          NOT QUOTED YET
                        </span>
                      )}
                    </div>

                    <div className="font-heading text-sm font-medium text-meridian-ink mb-2 line-clamp-2">
                      {auction.title}
                    </div>

                    {/* Corridor */}
                    <div className="text-xs font-mono text-meridian-muted flex items-center gap-1.5 mb-4">
                      <span className="truncate max-w-[110px] text-meridian-ink">{auction.origin}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-meridian-muted shrink-0" />
                      <span className="truncate max-w-[110px] text-meridian-ink">{auction.destination}</span>
                    </div>

                    {/* Standing Price Comparison Box */}
                    <div className="p-3 bg-meridian-surfaceDeep border border-meridian-line font-mono text-xs mb-4 space-y-1.5">
                      <div className="flex justify-between items-baseline">
                        <span className="text-meridian-muted text-[10px] uppercase tracking-wider">Leading (L1):</span>
                        <span className="font-bold text-meridian-ink tabular-nums">
                          {auction.lowest_bid ? `$${auction.lowest_bid.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                        </span>
                      </div>
                      <div className="flex justify-between items-baseline pt-1 border-t border-meridian-line">
                        <span className="text-meridian-muted text-[10px] uppercase tracking-wider">Your Best:</span>
                        <span className="font-bold tabular-nums text-meridian-ink">
                          {auction.my_bid ? `$${auction.my_bid.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : 'Not quoted'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Countdown & Action */}
                  <div className="pt-2 border-t border-meridian-line">
                    <div className="flex items-center justify-between text-xs font-mono mb-3">
                      <span className="text-meridian-muted">Time left:</span>
                      <CountdownTimer targetDate={auction.effective_close} size="sm" theme="light" />
                    </div>

                    <Link
                      to={`/live/${auction.id}`}
                      className="btn-primary w-full py-2.5 font-mono text-xs uppercase tracking-wider flex items-center justify-center gap-2"
                    >
                      <Radio className="w-3.5 h-3.5" />
                      <span>Enter Live Room</span>
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Recent Bids History */}
      <div>
        <SectionHeader
          railLabel="02 / BID HISTORY"
          title="Your Submitted Freight Quotes"
          description="Historical record of quotes submitted by your organization across all RFQs."
        />

        <HairlineTable>
          {recent_bids.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={6} className="py-12 text-center text-meridian-muted font-mono text-xs">
                  No bids submitted yet. Select an active auction above to submit your first competitive quote.
                </td>
              </tr>
            </tbody>
          ) : (
            <>
              <thead>
                <tr className="bg-meridian-surfaceDeep border-b border-meridian-line text-meridian-muted text-[11px] font-mono uppercase tracking-[0.08em]">
                  <th className="py-3 px-4">UTC Timestamp</th>
                  <th className="py-3 px-4">RFQ Identifier</th>
                  <th className="py-3 px-4">Operating Carrier</th>
                  <th className="py-3 px-4">Transit Days</th>
                  <th className="py-3 px-4 text-right">Total Committed Rate</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-meridian-line font-mono text-xs">
                {recent_bids.map((b) => (
                  <tr key={b.bid_id} className="hover:bg-meridian-surfaceDeep transition-colors">
                    <td className="py-2.5 px-4 text-meridian-muted tabular-nums">
                      {format(new Date(b.created_at), 'MMM dd HH:mm:ss')} UTC
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-meridian-ink">
                      {b.rfq_ref}
                    </td>
                    <td className="py-2.5 px-4 text-meridian-ink">
                      {b.carrier_name}
                    </td>
                    <td className="py-2.5 px-4 text-meridian-ink tabular-nums">
                      {b.transit_time_days}d
                    </td>
                    <td className="py-2.5 px-4 text-right font-bold text-meridian-ink tabular-nums text-sm">
                      ${b.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <Link
                        to={`/live/${b.rfq_id}`}
                        className="text-meridian-ink hover:underline font-medium text-xs inline-flex items-center gap-1"
                      >
                        Enter Room →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </>
          )}
        </HairlineTable>
      </div>

    </div>
  );
};
