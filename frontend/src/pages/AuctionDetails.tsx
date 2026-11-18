import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { RFQ, Bid, AuctionEvent } from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { StatusChip, HairlineTable } from '../components/common/Primitives';
import { 
  ArrowLeft, 
  Radio, 
  MapPin, 
  Calendar, 
  AlertTriangle,
  RefreshCw,
  Download,
  Award,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  TrendingDown,
  Clock,
  Layers,
  X
} from 'lucide-react';
import { format } from 'date-fns';

export const AuctionDetails: React.FC = () => {
  const { rfqId } = useParams<{ rfqId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [rfq, setRfq] = useState<RFQ | null>(null);
  const [bids, setBids] = useState<Bid[]>([]);
  const [events, setEvents] = useState<AuctionEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Replay State
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Award Modal State
  const [showAwardModal, setShowAwardModal] = useState<boolean>(false);
  const [selectedBidId, setSelectedBidId] = useState<string>('');
  const [awardReason, setAwardReason] = useState<string>('Lowest verified rate and carrier transit SLA compliance');
  const [awardNotes, setAwardNotes] = useState<string>('');
  const [isSubmittingAward, setIsSubmittingAward] = useState<boolean>(false);

  const isBuyer = user?.role === 'buyer';

  const loadData = async () => {
    if (!rfqId) return;
    try {
      const [rfqData, bidsData, eventsData] = await Promise.all([
        api.getRfq(rfqId),
        api.listBids(rfqId),
        api.getRfqEvents(rfqId),
      ]);
      setRfq(rfqData);
      setBids(bidsData);
      setEvents(eventsData);
      setReplayIndex(bidsData.length);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load auction details.');
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [rfqId]);

  // Handle Play/Pause in Replay
  useEffect(() => {
    let timer: any = null;
    if (isPlaying && bids.length > 0) {
      timer = setInterval(() => {
        setReplayIndex((prev) => {
          if (prev >= bids.length) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1200);
    }
    return () => clearInterval(timer);
  }, [isPlaying, bids.length]);

  // Compute award record if already awarded
  const awardRecord = useMemo(() => {
    const ev = events.find((e) => e.event_type === 'AUCTION_AWARDED');
    return ev ? ev.payload : null;
  }, [events]);

  // Sorted bids chronologically
  const chronologicalBids = useMemo(() => {
    return [...bids].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, [bids]);

  // Replay sliced bids up to replayIndex
  const activeReplayBids = useMemo(() => {
    if (replayIndex === 0) return [];
    return chronologicalBids.slice(0, replayIndex);
  }, [chronologicalBids, replayIndex]);

  // Dynamically compute ladder at current replay point
  const replayRankings = useMemo(() => {
    const latestBySupplier = new Map<string, Bid>();
    for (const b of activeReplayBids) {
      latestBySupplier.set(b.supplier_id, b);
    }
    const ranked = Array.from(latestBySupplier.values());
    ranked.sort((a, b) => {
      const diff = Number(a.total) - Number(b.total);
      if (diff !== 0) return diff;
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    });
    return ranked;
  }, [activeReplayBids]);

  // Savings Analytics: price drop from first bid to final L1
  const savings = useMemo(() => {
    if (chronologicalBids.length < 2) return null;
    const firstBid = Number(chronologicalBids[0].total);
    const sorted = [...bids].sort((a, b) => Number(a.total) - Number(b.total));
    const finalL1 = Number(sorted[0].total);
    const diff = firstBid - finalL1;
    const pct = firstBid > 0 ? (diff / firstBid) * 100 : 0;
    return { firstBid, finalL1, diff, pct };
  }, [bids, chronologicalBids]);

  const handleDownloadCsv = () => {
    if (!rfqId) return;
    const token = localStorage.getItem('meridian_token');
    fetch(`/api/v1/rfqs/${rfqId}/export-csv`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => res.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `meridian_${rfq?.reference_id || 'auction'}_audit.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch((err) => alert('Export failed: ' + err.message));
  };

  const handleConfirmAward = async () => {
    if (!rfqId || !selectedBidId) return;
    try {
      setIsSubmittingAward(true);
      await api.awardRfq(rfqId, {
        winning_bid_id: selectedBidId,
        award_reason: awardReason,
        notes: awardNotes,
      });
      setIsSubmittingAward(false);
      setShowAwardModal(false);
      await loadData();
    } catch (err: any) {
      alert('Award failed: ' + (err.message || 'Unknown error'));
      setIsSubmittingAward(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-24 text-center font-mono text-sm text-meridian-muted flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-meridian-ink" />
        Loading Auction Historical Ledger...
      </div>
    );
  }

  if (error || !rfq) {
    return (
      <div className="p-8 bg-meridian-surface border border-meridian-line text-center font-mono">
        <AlertTriangle className="w-8 h-8 text-meridian-orange mx-auto mb-2" />
        <div className="text-base text-meridian-ink font-bold">{error || 'Auction not found'}</div>
        <button
          onClick={() => navigate('/auctions')}
          className="btn-secondary mt-4 px-4 py-2 text-xs"
        >
          Return to Auctions
        </button>
      </div>
    );
  }

  const isActive = rfq.status === 'ACTIVE';
  const isConcluded = rfq.status === 'CLOSED' || rfq.status === 'FORCE_CLOSED';

  return (
    <div className="space-y-8 pb-16 text-meridian-ink">
      
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-meridian-line font-mono text-xs">
        <div className="flex items-center gap-2 sm:gap-3 text-meridian-muted">
          <button
            onClick={() => navigate('/auctions')}
            className="flex items-center gap-1 hover:text-meridian-ink transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Auctions</span>
          </button>
          <span>/</span>
          <span className="text-meridian-ink font-bold">{rfq.reference_id}</span>
          <span>/</span>
          <span className="text-meridian-ink uppercase">Historical Audit & Timeline</span>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Download CSV button */}
          <button
            onClick={handleDownloadCsv}
            className="btn-secondary px-3 py-1.5 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5"
            title="Download audit-ready CSV of all bids"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          {/* Award Button for Buyer when concluded */}
          {isBuyer && isConcluded && !awardRecord && (
            <button
              onClick={() => {
                if (rfq.rankings && rfq.rankings.length > 0) {
                  setSelectedBidId(rfq.rankings[0].bid_id);
                }
                setShowAwardModal(true);
              }}
              className="btn-primary px-3 py-1.5 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5"
            >
              <Award className="w-3.5 h-3.5" />
              <span>Award RFQ</span>
            </button>
          )}

          {isActive && (
            <Link
              to={`/live/${rfq.id}`}
              className="btn-primary px-3 py-1.5 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5"
            >
              <Radio className="w-3.5 h-3.5" />
              <span>Enter Room</span>
            </Link>
          )}

          <button
            onClick={loadData}
            className="p-1.5 text-meridian-muted hover:text-meridian-ink transition-colors"
            title="Refresh historical data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Official Award Banner if awarded */}
      {awardRecord && (
        <div className="bg-meridian-lime/20 border-2 border-meridian-graphite p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-meridian-lime border border-meridian-graphite flex items-center justify-center shrink-0">
              <Award className="w-6 h-6 text-meridian-graphite" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-meridian-graphite">
                  CONTRACT AWARDED
                </span>
                <span className="text-[10px] bg-meridian-graphite text-meridian-ivory px-1.5 py-0.2 uppercase font-bold">
                  OFFICIAL
                </span>
              </div>
              <div className="text-sm font-bold text-meridian-ink mt-0.5">
                Awarded to {awardRecord.carrier_name} at ${Number(awardRecord.total).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-xs text-meridian-muted font-sans mt-0.5">
                Reason: {awardRecord.award_reason}
              </p>
            </div>
          </div>
          <div className="text-right text-[11px] text-meridian-muted shrink-0">
            <div>Awarded by {awardRecord.awarded_by}</div>
            <div className="tabular-nums">{format(new Date(awardRecord.awarded_at), 'yyyy-MM-dd HH:mm:ss')} UTC</div>
          </div>
        </div>
      )}

      {/* Main Header Specs Card */}
      <div className="bg-meridian-surface border border-meridian-line p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <StatusChip status={rfq.status} size="sm" />
              <span className="text-xs font-mono text-meridian-muted">
                Created {format(new Date(rfq.created_at), 'MMM dd, yyyy HH:mm')} UTC
              </span>
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-medium text-meridian-ink tracking-tight">
              {rfq.title}
            </h1>
            <p className="text-xs text-meridian-muted font-sans mt-2 max-w-2xl leading-relaxed">
              {rfq.description || 'No detailed service specs provided.'}
            </p>
          </div>

          {/* Timing Parameters Box */}
          <div className="bg-meridian-surfaceDeep border border-meridian-line p-4 font-mono text-xs min-w-[260px]">
            <div className="text-[11px] uppercase tracking-[0.08em] text-meridian-muted mb-2 flex justify-between">
              <span>Auction Timing</span>
              <span className="font-bold text-meridian-ink bg-meridian-surface px-1.5 py-0.5 border border-meridian-line">
                {rfq.config?.trigger_type}
              </span>
            </div>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex justify-between">
                <span className="text-meridian-muted">Scheduled Close:</span>
                <span className="text-meridian-ink font-semibold tabular-nums">{format(new Date(rfq.bid_close), 'HH:mm:ss')} UTC</span>
              </div>
              <div className="flex justify-between">
                <span className="text-meridian-muted">Effective Close:</span>
                <span className="text-meridian-ink font-bold tabular-nums">{format(new Date(rfq.effective_close), 'HH:mm:ss')} UTC</span>
              </div>
              <div className="flex justify-between">
                <span className="text-meridian-muted">Forced Close:</span>
                <span className="text-meridian-ink font-bold tabular-nums">{format(new Date(rfq.forced_close), 'HH:mm:ss')} UTC</span>
              </div>
              <div className="pt-2 border-t border-meridian-line text-[10px] text-meridian-muted">
                Rule: X={rfq.config?.trigger_window_minutes}m trigger window, Y={rfq.config?.extension_minutes}m dynamic extension
              </div>
            </div>
          </div>
        </div>

        {/* Corridor Details Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6 pt-6 border-t border-meridian-line font-mono text-xs">
          <div className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-meridian-muted" />
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Origin Corridor</span>
              <span className="font-bold text-meridian-ink">{rfq.origin}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-meridian-muted" />
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Destination Corridor</span>
              <span className="font-bold text-meridian-ink">{rfq.destination}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-meridian-muted" />
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Target Pickup</span>
              <span className="font-bold text-meridian-ink">{format(new Date(rfq.pickup_date), 'MMM dd, yyyy')}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Savings Analytics Card */}
      {savings && (
        <div className="bg-meridian-surfaceDeep border border-meridian-line p-4 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-meridian-line">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-meridian-lime stroke-[2.5]" />
              <span className="font-bold uppercase tracking-wider text-meridian-ink">Procurement Savings Analytics</span>
            </div>
            <span className="text-[11px] text-meridian-muted">
              {bids.length} total bids across {rfq.participating_suppliers_count} carriers
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Opening Quote</span>
              <span className="text-sm font-bold text-meridian-ink tabular-nums">${savings.firstBid.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Final Lowest (L1)</span>
              <span className="text-sm font-bold text-meridian-ink tabular-nums">${savings.finalL1.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Total Price Compression</span>
              <span className="text-sm font-bold text-meridian-ink tabular-nums">-${savings.diff.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
            <div>
              <span className="text-[10px] text-meridian-muted uppercase block">Savings Yield</span>
              <span className="text-sm font-bold text-meridian-lime tabular-nums bg-meridian-graphite px-2 py-0.5 inline-block">
                {savings.pct.toFixed(1)}% Reductions
              </span>
            </div>
          </div>
        </div>
      )}

      {/* FEATURE 1: Interactive Auction Replay Scrubber */}
      {chronologicalBids.length > 0 && (
        <div className="bg-meridian-surface border border-meridian-line p-5 font-mono text-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-meridian-line pb-3">
            <div>
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-meridian-ink" />
                <h3 className="font-bold text-xs uppercase tracking-wider text-meridian-ink">
                  Auction Replay & Sequence Scrubber
                </h3>
              </div>
              <p className="text-[11px] text-meridian-muted mt-0.5">
                Scrub through historical bid progression to replay rank swaps and price discoveries.
              </p>
            </div>

            {/* Play/Pause & Step Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="btn-secondary px-2.5 py-1 text-xs flex items-center gap-1.5 uppercase font-bold"
              >
                {isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                <span>{isPlaying ? 'Pause' : 'Play'}</span>
              </button>
              <button
                onClick={() => { setIsPlaying(false); setReplayIndex(0); }}
                className="btn-secondary px-2 py-1 text-xs"
                title="Reset to beginning"
              >
                <RotateCcw className="w-3 h-3" />
              </button>
              <span className="text-meridian-muted text-[11px] tabular-nums pl-1">
                Tick {replayIndex} of {chronologicalBids.length}
              </span>
            </div>
          </div>

          {/* Slider input */}
          <div>
            <input
              type="range"
              min="0"
              max={chronologicalBids.length}
              value={replayIndex}
              onChange={(e) => {
                setIsPlaying(false);
                setReplayIndex(Number(e.target.value));
              }}
              className="w-full h-1.5 bg-meridian-surfaceDeep appearance-none cursor-pointer accent-meridian-graphite"
            />
          </div>

          {/* Replay Rank Ladder Snapshot */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
            {replayRankings.map((b, idx) => (
              <div
                key={b.supplier_id}
                className={`p-3 border ${
                  idx === 0 
                    ? 'border-meridian-graphite bg-meridian-lime/15' 
                    : 'border-meridian-line bg-meridian-surfaceDeep'
                }`}
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-meridian-ink uppercase">Rank {idx + 1}</span>
                  <span className="text-meridian-muted">{b.carrier_name}</span>
                </div>
                <div className="text-lg font-bold text-meridian-ink tabular-nums mt-1">
                  ${Number(b.total).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-[10px] text-meridian-muted mt-1 tabular-nums">
                  {format(new Date(b.created_at), 'HH:mm:ss')} UTC · {b.transit_time_days}d transit
                </div>
              </div>
            ))}
            {replayRankings.length === 0 && (
              <div className="col-span-3 text-center py-4 text-meridian-muted">
                Beginning of auction. No bids submitted yet. Drag slider forward.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Committed Quotes Ledger */}
      <div>
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-meridian-line">
          <div>
            <h2 className="font-heading text-lg font-medium text-meridian-ink tracking-tight">
              All Submitted Carrier Quotes
            </h2>
            <p className="text-xs text-meridian-muted mt-0.5">
              Ranked and immutable audit log of every binding quote submitted on this exchange.
            </p>
          </div>
          <span className="font-mono text-xs text-meridian-muted">
            {bids.length} Total Quotes
          </span>
        </div>

        <HairlineTable>
          <thead>
            <tr className="bg-meridian-surfaceDeep border-b border-meridian-line text-meridian-muted text-[11px] font-mono uppercase tracking-[0.08em]">
              <th className="py-3 px-4">Timestamp</th>
              <th className="py-3 px-4">Carrier Name</th>
              <th className="py-3 px-4">Freight</th>
              <th className="py-3 px-4">Origin</th>
              <th className="py-3 px-4">Destination</th>
              <th className="py-3 px-4">Total</th>
              <th className="py-3 px-4">Transit</th>
              <th className="py-3 px-4">Validity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-meridian-line font-mono text-xs">
            {bids.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-meridian-muted font-mono text-xs">
                  No bids recorded for this exchange.
                </td>
              </tr>
            ) : (
              bids.map((b) => (
                <tr key={b.id} className="hover:bg-meridian-surfaceDeep transition-colors font-mono text-xs">
                  <td className="py-2.5 px-4 text-meridian-muted tabular-nums">
                    {format(new Date(b.created_at), 'MMM dd, HH:mm:ss')}
                  </td>
                  <td className="py-2.5 px-4 font-semibold text-meridian-ink">
                    {b.carrier_name}
                  </td>
                  <td className="py-2.5 px-4 tabular-nums">${Number(b.freight_charges).toFixed(2)}</td>
                  <td className="py-2.5 px-4 tabular-nums">${Number(b.origin_charges).toFixed(2)}</td>
                  <td className="py-2.5 px-4 tabular-nums">${Number(b.destination_charges).toFixed(2)}</td>
                  <td className="py-2.5 px-4 font-bold text-meridian-ink tabular-nums">
                    ${Number(b.total).toFixed(2)}
                  </td>
                  <td className="py-2.5 px-4 tabular-nums">{b.transit_time_days} days</td>
                  <td className="py-2.5 px-4 text-meridian-muted tabular-nums">
                    {format(new Date(b.quote_validity_date), 'yyyy-MM-dd')}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </HairlineTable>
      </div>

      {/* Chronological Audit Trail & Extensions */}
      <div>
        <div className="flex items-center justify-between pb-3 mb-6 border-b border-meridian-line">
          <div>
            <h2 className="font-heading text-lg font-medium text-meridian-ink tracking-tight">
              Chronological Audit Trail & Extensions
            </h2>
            <p className="text-xs text-meridian-muted mt-0.5">
              Complete timeline of bids, dynamic soft-close extensions, and closure events.
            </p>
          </div>
          <span className="font-mono text-xs text-meridian-muted">
            {events.length} Events
          </span>
        </div>

        {/* 1px Graphite spine on ivory */}
        <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-px before:bg-meridian-ink font-mono text-xs">
          {events.map((ev) => {
            const isExtension = ev.event_type === 'EXTENSION_APPLIED';
            const isCapped = ev.event_type === 'EXTENSION_CAPPED';
            const isBid = ev.event_type === 'BID_SUBMITTED' || ev.event_type === 'L1_CHANGED';
            const isAward = ev.event_type === 'AUCTION_AWARDED';

            return (
              <div key={ev.id} className="relative">
                {/* Square marker on timeline */}
                <div
                  className={`absolute -left-[28px] top-1.5 w-2.5 h-2.5 rounded-none border ${
                    isAward
                      ? 'bg-meridian-lime border-meridian-graphite'
                      : isBid
                      ? 'bg-meridian-lime border-meridian-ink'
                      : isExtension || isCapped
                      ? 'bg-meridian-orange border-meridian-ink'
                      : 'bg-meridian-ink border-meridian-ink'
                  }`}
                />

                <div className="bg-meridian-surface border border-meridian-line p-4">
                  <div className="flex items-center justify-between text-[11px] mb-1">
                    <span className="font-bold uppercase tracking-wider text-meridian-ink flex items-center gap-2">
                      {ev.event_type}
                      {isAward && (
                        <span className="px-1.5 py-0.2 bg-meridian-lime text-meridian-graphite text-[9px] font-bold">
                          AWARDED
                        </span>
                      )}
                    </span>
                    <span className="text-meridian-muted tabular-nums">
                      {format(new Date(ev.created_at), 'MMM dd, yyyy HH:mm:ss')} UTC
                    </span>
                  </div>

                  {ev.payload?.reason && (
                    <p className="font-sans text-xs text-meridian-ink leading-relaxed mt-1">
                      {ev.payload.reason}
                    </p>
                  )}

                  {ev.payload?.award_reason && (
                    <p className="font-sans text-xs font-semibold text-meridian-graphite leading-relaxed mt-1">
                      Award Justification: {ev.payload.award_reason}
                    </p>
                  )}

                  {ev.payload?.new_close && (
                    <div className="mt-1.5 text-xs text-meridian-ink font-bold font-mono">
                      New Effective Close: {format(new Date(ev.payload.new_close), 'HH:mm:ss')} UTC
                      {ev.payload.is_clamped && (
                        <span className="ml-2 px-1.5 py-0.2 bg-meridian-orange text-meridian-ink text-[10px] uppercase font-bold">
                          CLAMPED
                        </span>
                      )}
                    </div>
                  )}

                  {ev.payload?.total && (
                    <div className="mt-1 text-xs text-meridian-muted font-mono">
                      Committed Total: <span className="font-bold text-meridian-ink tabular-nums">${Number(ev.payload.total).toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Award Selection Modal */}
      {showAwardModal && (
        <div className="fixed inset-0 z-50 bg-meridian-graphite/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-meridian-surface border-2 border-meridian-graphite max-w-md w-full p-6 font-mono space-y-4 shadow-float">
            <div className="flex items-center justify-between pb-3 border-b border-meridian-line">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-meridian-graphite" />
                <h3 className="font-bold text-sm uppercase tracking-wider text-meridian-ink">
                  Award Procurement Contract
                </h3>
              </div>
              <button
                onClick={() => setShowAwardModal(false)}
                className="text-meridian-muted hover:text-meridian-ink"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[10px] text-meridian-muted uppercase block mb-1">
                  Select Winning Carrier Quote:
                </label>
                <select
                  value={selectedBidId}
                  onChange={(e) => setSelectedBidId(e.target.value)}
                  className="w-full bg-meridian-surfaceDeep border border-meridian-line p-2 text-xs font-mono text-meridian-ink outline-none"
                >
                  {bids.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.carrier_name} — ${Number(b.total).toLocaleString('en-US', { minimumFractionDigits: 2 })} ({b.transit_time_days}d transit)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] text-meridian-muted uppercase block mb-1">
                  Award Justification:
                </label>
                <input
                  type="text"
                  value={awardReason}
                  onChange={(e) => setAwardReason(e.target.value)}
                  placeholder="Justification for executive procurement signoff"
                  className="w-full bg-meridian-surfaceDeep border border-meridian-line p-2 text-xs font-mono text-meridian-ink outline-none"
                />
              </div>

              <div>
                <label className="text-[10px] text-meridian-muted uppercase block mb-1">
                  Procurement Committee Notes:
                </label>
                <textarea
                  value={awardNotes}
                  onChange={(e) => setAwardNotes(e.target.value)}
                  rows={3}
                  placeholder="Additional contractual notes..."
                  className="w-full bg-meridian-surfaceDeep border border-meridian-line p-2 text-xs font-mono text-meridian-ink outline-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-meridian-line">
              <button
                onClick={() => setShowAwardModal(false)}
                className="btn-secondary px-3 py-1.5 text-xs font-mono uppercase"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAward}
                disabled={isSubmittingAward || !selectedBidId}
                className="btn-primary px-4 py-1.5 text-xs font-mono uppercase font-bold flex items-center gap-1.5"
              >
                {isSubmittingAward && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Confirm & Sign Award</span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
