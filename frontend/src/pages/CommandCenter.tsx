import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { CommandCenterMetrics } from '../types';
import { CountdownTimer } from '../components/common/CountdownTimer';
import { InstrumentPanel, SectionHeader, HairlineTable } from '../components/common/Primitives';
import { 
  PlusCircle, 
  RefreshCw, 
  Radio, 
  ArrowUpRight, 
  AlertTriangle,
  Clock
} from 'lucide-react';
import { format } from 'date-fns';

export const CommandCenter: React.FC = () => {
  const [metrics, setMetrics] = useState<CommandCenterMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      const data = await api.getCommandCenter();
      setMetrics(data);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load command center data');
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
        Loading Procurement Command Center...
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

  const { summary, upcoming_deadlines, recent_activity, performance } = metrics;
  const nextToClose = upcoming_deadlines.length > 0 ? upcoming_deadlines[0] : null;

  return (
    <div className="space-y-16 pb-12">
      
      {/* 1. Header with Faint 8px Technical Grid (4% Opacity) */}
      <div className="technical-grid p-6 -mx-4 sm:-mx-6 lg:-mx-8 border-b border-meridian-line">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted flex items-center gap-2 mb-2">
              <span>MERIDIAN SYSTEM</span>
              <span>/</span>
              <span className="text-meridian-ink font-semibold">BUYER COMMAND CENTER</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-heading font-medium tracking-tight text-meridian-ink">
              Procurement Exchange
            </h1>
            <p className="text-sm text-meridian-muted mt-2 max-w-xl leading-relaxed">
              Real-time British Auction trading terminal. Authoritative server-side soft close, automated dynamic extension, and row-locked ledger settlement.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/create-rfq"
              className="btn-primary px-4 py-2.5 font-mono text-xs uppercase tracking-wider flex items-center gap-2"
            >
              <PlusCircle className="w-4 h-4" />
              Create RFQ
            </Link>
            <button
              onClick={fetchMetrics}
              className="btn-secondary p-2.5"
              title="Refresh metrics"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 2. THE SINGLE DARK ELEMENT: Next to Close Strip (<15% screen area) */}
      {nextToClose && (
        <InstrumentPanel className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="px-2.5 py-1 bg-meridian-orange text-meridian-ink font-mono font-bold text-xs uppercase tracking-wider">
              NEXT TO CLOSE
            </div>
            <div>
              <div className="flex items-center gap-2 text-white/70 font-mono text-xs">
                <span className="font-bold text-white">{nextToClose.reference_id}</span>
                <span>•</span>
                <span>{nextToClose.bids_count} bids placed</span>
              </div>
              <div className="text-base font-heading font-semibold text-white mt-0.5">
                {nextToClose.title}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <span className="font-mono text-[10px] text-white/60 uppercase block">Leading L1 Quote</span>
              <span className="font-mono font-bold text-base text-meridian-lime tabular-nums">
                {nextToClose.lowest_bid ? `$${nextToClose.lowest_bid.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
              </span>
            </div>

            <div className="text-right border-l border-white/15 pl-5">
              <span className="font-mono text-[10px] text-white/60 uppercase block">Time Remaining</span>
              <CountdownTimer targetDate={nextToClose.effective_close} size="md" theme="dark" />
            </div>

            <Link
              to={`/live/${nextToClose.id}`}
              className="px-3.5 py-2 bg-meridian-lime text-meridian-ink font-mono font-bold text-xs uppercase tracking-wider hover:opacity-95 flex items-center gap-1.5 shrink-0"
            >
              <Radio className="w-3.5 h-3.5" />
              <span>Enter Room</span>
            </Link>
          </div>
        </InstrumentPanel>
      )}

      {/* 3. Large Editorial Numerals on Ivory Separated by Hairlines */}
      <div>
        <div className="grid grid-cols-2 lg:grid-cols-4 border-y border-meridian-line divide-x divide-meridian-line py-6">
          
          {/* Stat 1 */}
          <div className="px-4 sm:px-6 py-2">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
              01 / RFQ Volume
            </span>
            <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums">
              {summary.total_rfqs}
            </div>
            <div className="mt-2 text-xs font-mono text-meridian-muted flex items-center gap-2">
              <span className="font-bold text-meridian-ink">{summary.active_count} Active</span>
              <span>•</span>
              <span>{summary.scheduled_count} Sched.</span>
            </div>
          </div>

          {/* Stat 2 */}
          <div className="px-4 sm:px-6 py-2">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
              02 / Yield Reduction
            </span>
            <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums">
              -{summary.avg_price_reduction_pct}%
            </div>
            <p className="mt-2 text-xs font-mono text-meridian-muted">
              1st quote to final L1 · {summary.avg_extensions_per_auction || 0} avg. extensions
            </p>
          </div>

          {/* Stat 3 */}
          <div className="px-4 sm:px-6 py-2">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
              03 / Ledger Bids
            </span>
            <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums">
              {summary.total_bids}
            </div>
            <p className="mt-2 text-xs font-mono text-meridian-muted">
              Row-locked transactions
            </p>
          </div>

          {/* Stat 4 */}
          <div className="px-4 sm:px-6 py-2">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-2">
              04 / Carrier Network
            </span>
            <div className="font-mono text-4xl sm:text-5xl font-medium text-meridian-ink tabular-nums">
              {summary.participating_suppliers}
            </div>
            <p className="mt-2 text-xs font-mono text-meridian-muted">
              Active commercial liners
            </p>
          </div>

        </div>
      </div>

      {/* 4. Asymmetrical 7 / 5 Grid: Watchlist & Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        
        {/* Left (7 cols): Imminent Watchlist */}
        <div className="lg:col-span-7">
          <SectionHeader
            railLabel="01 / WATCHLIST"
            title="Imminent Auction Deadlines"
            description="Active auctions sorted by closing deadline. Soft close trigger windows monitored."
            action={
              <Link to="/auctions" className="text-xs font-mono font-medium text-meridian-ink hover:underline flex items-center gap-1">
                All Auctions <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            }
          />

          <div className="border border-meridian-line bg-meridian-surface divide-y divide-meridian-line">
            {upcoming_deadlines.length === 0 ? (
              <div className="py-12 text-center text-meridian-muted font-mono text-xs">
                No active auctions closing soon.
              </div>
            ) : (
              upcoming_deadlines.map((rfq) => (
                <div
                  key={rfq.id}
                  className="p-4 hover:bg-meridian-surfaceDeep transition-colors flex flex-wrap items-center justify-between gap-4"
                >
                  <div className="flex-1 min-w-[200px]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-xs font-bold text-meridian-ink">
                        {rfq.reference_id}
                      </span>
                      <span className="text-[11px] font-mono text-meridian-muted">
                        • {rfq.bids_count} bids
                      </span>
                    </div>
                    <div className="text-sm font-medium text-meridian-ink truncate max-w-sm">
                      {rfq.title}
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="font-mono text-[10px] text-meridian-muted uppercase block">
                      Leading L1
                    </span>
                    <span className="font-mono font-bold text-sm text-meridian-ink tabular-nums">
                      {rfq.lowest_bid ? `$${rfq.lowest_bid.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <span className="font-mono text-[10px] text-meridian-muted uppercase block">
                        Closing In
                      </span>
                      <CountdownTimer targetDate={rfq.effective_close} size="sm" theme="light" />
                    </div>
                    <Link
                      to={`/live/${rfq.id}`}
                      className="btn-primary px-3 py-1.5 text-xs font-mono uppercase tracking-wider flex items-center gap-1"
                    >
                      <Radio className="w-3 h-3" />
                      <span>Room</span>
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right (5 cols): Yield Performance */}
        <div className="lg:col-span-5">
          <SectionHeader
            railLabel="02 / YIELD ANALYSIS"
            title="Price Compression by RFQ"
            description="Reduction percentage between first received quote and final L1 rate."
          />

          <div className="border border-meridian-line bg-meridian-surface p-5 space-y-4">
            {performance.slice(0, 5).map((item, idx) => (
              <div key={idx} className="font-mono text-xs pb-3 border-b border-meridian-line last:border-b-0 last:pb-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold text-meridian-ink truncate max-w-[200px]">
                    {item.rfq_ref}
                  </span>
                  <span className="font-bold text-meridian-ink bg-meridian-lime px-2 py-0.5 border border-meridian-ink text-[11px]">
                    -{item.reduction_pct}% yield
                  </span>
                </div>

                {/* Performance Graphic Line */}
                <div className="w-full h-2 bg-meridian-surfaceDeep border border-meridian-line mb-2">
                  <div
                    className="h-full bg-meridian-ink"
                    style={{ width: `${Math.min(100, Math.max(10, item.reduction_pct * 3.5))}%` }}
                  />
                </div>

                <div className="flex justify-between text-[11px] text-meridian-muted">
                  <span>Initial: ${item.first_bid.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                  <span className="font-semibold text-meridian-ink">
                    L1: ${item.current_l1.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* 5. Platform-Wide Immutable Audit Log */}
      <div>
        <SectionHeader
          railLabel="03 / AUDIT STREAM"
          title="Platform Transaction Log"
          description="Append-only immutable record of authoritative bids, extensions, and deadline transitions."
        />

        <HairlineTable>
          <thead>
            <tr className="bg-meridian-surfaceDeep border-b border-meridian-line text-meridian-muted text-[11px] font-mono uppercase tracking-[0.08em]">
              <th className="py-3 px-4">UTC Timestamp</th>
              <th className="py-3 px-4">RFQ Identifier</th>
              <th className="py-3 px-4">Event Type</th>
              <th className="py-3 px-4">Event Payload / Reason</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-meridian-line font-mono text-xs">
            {recent_activity.map((ev) => (
              <tr key={ev.id} className="hover:bg-meridian-surfaceDeep transition-colors">
                <td className="py-2.5 px-4 text-meridian-muted tabular-nums">
                  {format(new Date(ev.created_at), 'MMM dd HH:mm:ss')}
                </td>
                <td className="py-2.5 px-4 font-semibold text-meridian-ink">
                  {ev.rfq_ref}
                </td>
                <td className="py-2.5 px-4">
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-meridian-surfaceDeep border border-meridian-line uppercase text-meridian-ink">
                    {ev.event_type}
                  </span>
                </td>
                <td className="py-2.5 px-4 text-meridian-ink truncate max-w-sm">
                  {ev.payload?.total ? `Rate: $${Number(ev.payload.total).toFixed(2)}` : ''}
                  {ev.payload?.reason ? `${ev.payload.reason}` : ''}
                  {ev.payload?.new_l1_total ? `New L1: $${Number(ev.payload.new_l1_total).toFixed(2)}` : ''}
                </td>
                <td className="py-2.5 px-4 text-right">
                  <Link
                    to={`/live/${ev.rfq_id}`}
                    className="text-meridian-ink hover:underline font-medium text-xs inline-flex items-center gap-1"
                  >
                    Live Room →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </HairlineTable>
      </div>

    </div>
  );
};
