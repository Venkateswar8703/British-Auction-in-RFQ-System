import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { RFQ } from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { StatusChip } from '../components/common/Primitives';
import { CountdownTimer } from '../components/common/CountdownTimer';
import { 
  Search, 
  ArrowUp, 
  ArrowDown, 
  ArrowUpDown, 
  Radio, 
  FileText, 
  PlusCircle, 
  AlertTriangle,
  ArrowRight,
  FilterX,
  Check
} from 'lucide-react';
import { extractLocode, formatAuctionDateParts } from '../utils/auction';

export const AuctionListing: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [closingSoonOnly, setClosingSoonOnly] = useState<boolean>(false);
  const [myBidsOnly, setMyBidsOnly] = useState<boolean>(false);

  // Timezone setting: default to Local and persist in localStorage
  const [isUtc, setIsUtc] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('meridian_tz_preference');
      return saved === 'UTC';
    } catch {
      return false;
    }
  });

  const handleTimezoneChange = (utc: boolean) => {
    setIsUtc(utc);
    try {
      localStorage.setItem('meridian_tz_preference', utc ? 'UTC' : 'LOCAL');
    } catch {
      // Ignore storage errors
    }
  };

  // Sorting: null means use default British priority order
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const isBuyer = user?.role === 'buyer';

  const fetchRfqs = async () => {
    try {
      setError(null);
      const data = await api.listRfqs();
      setRfqs(data);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load auction directory');
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRfqs();
    const interval = setInterval(fetchRfqs, 10000);
    return () => clearInterval(interval);
  }, []);

  // Compute status counts across all loaded RFQs
  const counts = useMemo(() => {
    const res = { ALL: rfqs.length, ACTIVE: 0, SCHEDULED: 0, CLOSED: 0, FORCE_CLOSED: 0 };
    for (const r of rfqs) {
      if (r.status === 'ACTIVE') res.ACTIVE++;
      else if (r.status === 'SCHEDULED') res.SCHEDULED++;
      else if (r.status === 'CLOSED') res.CLOSED++;
      else if (r.status === 'FORCE_CLOSED') res.FORCE_CLOSED++;
    }
    return res;
  }, [rfqs]);

  // Client filtering & default British Auction ordering
  const displayedRfqs = useMemo(() => {
    let result = [...rfqs];
    const nowMs = Date.now();

    // 1. Status Filter
    if (statusFilter !== 'ALL') {
      result = result.filter((r) => r.status === statusFilter);
    }

    // 2. Closing Soon (<15m) filter
    if (closingSoonOnly) {
      result = result.filter((r) => {
        if (r.status !== 'ACTIVE') return false;
        const diff = new Date(r.effective_close).getTime() - nowMs;
        return diff > 0 && diff <= 15 * 60 * 1000;
      });
    }

    // 3. My Bids Only filter (for suppliers)
    if (myBidsOnly && !isBuyer) {
      result = result.filter((r) => Boolean(r.my_latest_bid));
    }

    // 4. Text Search (RFQ, port or carrier)
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((r) => {
        return (
          r.reference_id.toLowerCase().includes(q) ||
          r.title.toLowerCase().includes(q) ||
          r.origin.toLowerCase().includes(q) ||
          r.destination.toLowerCase().includes(q)
        );
      });
    }

    // 5. Sorting
    if (sortField) {
      result.sort((a, b) => {
        let valA: any = a[sortField as keyof RFQ];
        let valB: any = b[sortField as keyof RFQ];

        if (sortField === 'lowest_bid_total') {
          valA = valA ? Number(valA) : 999999999;
          valB = valB ? Number(valB) : 999999999;
        } else if (sortField === 'effective_close' || sortField === 'forced_close' || sortField === 'created_at') {
          valA = new Date(valA).getTime();
          valB = new Date(valB).getTime();
        }

        if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
        return 0;
      });
    } else {
      // DEFAULT BRITISH ORDER:
      // Active (soonest close first) -> Scheduled (soonest start first) -> Closed / Force Closed (newest first)
      result.sort((a, b) => {
        const orderPriority = (status: string) => {
          if (status === 'ACTIVE') return 1;
          if (status === 'SCHEDULED') return 2;
          return 3;
        };

        const pA = orderPriority(a.status);
        const pB = orderPriority(b.status);
        if (pA !== pB) return pA - pB;

        if (a.status === 'ACTIVE') {
          return new Date(a.effective_close).getTime() - new Date(b.effective_close).getTime();
        }
        if (a.status === 'SCHEDULED') {
          return new Date(a.bid_start).getTime() - new Date(b.bid_start).getTime();
        }
        // Concluded: newest close first
        return new Date(b.effective_close).getTime() - new Date(a.effective_close).getTime();
      });
    }

    return result;
  }, [rfqs, statusFilter, closingSoonOnly, myBidsOnly, search, sortField, sortDirection, isBuyer]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      if (sortDirection === 'asc') {
        setSortDirection('desc');
      } else {
        // Reset to default British order
        setSortField(null);
        setSortDirection('asc');
      }
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: string) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-meridian-muted opacity-60" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3.5 h-3.5 text-meridian-ink font-bold" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-meridian-ink font-bold" />
    );
  };

  const clearAllFilters = () => {
    setStatusFilter('ALL');
    setSearch('');
    setClosingSoonOnly(false);
    setMyBidsOnly(false);
    setSortField(null);
  };

  return (
    <div className="pt-10 space-y-6 pb-16 text-meridian-ink">
      
      {/* 1. Page Header (At least 40px below Nav bar) */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-meridian-line">
        <div>
          <div className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted flex items-center gap-2 mb-2">
            <span>EXCHANGES DIRECTORY</span>
            <span>/</span>
            <span className="text-meridian-ink font-semibold">ALL RFQS</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-heading font-medium tracking-tight text-meridian-ink">
            {isBuyer ? 'British Auction RFQ Directory' : 'Invited Freight Auctions'}
          </h1>
          <p className="text-sm text-meridian-muted mt-1 leading-relaxed">
            Real-time procurement exchanges with dynamic soft-close extension rules and authoritative server timers.
          </p>
        </div>

        {isBuyer && (
          <Link
            to="/create-rfq"
            className="btn-primary px-4 py-2 font-mono text-xs uppercase tracking-wider flex items-center gap-2 self-start md:self-auto shrink-0"
          >
            <PlusCircle className="w-4 h-4" />
            Create RFQ
          </Link>
        )}
      </div>

      {/* 2. Collapsed Toolbar: Status Tabs on Left, Urgency Toggles, Search & TZ on Right */}
      <div className="bg-meridian-surface border border-meridian-line p-2.5 flex flex-wrap lg:flex-nowrap items-center justify-between gap-3">
        
        {/* Left: Status tabs with exact counts */}
        <div className="flex items-center gap-1 font-mono text-xs overflow-x-auto shrink-0 pb-1 lg:pb-0">
          {[
            { key: 'ALL', label: `All (${counts.ALL})` },
            { key: 'ACTIVE', label: `Active (${counts.ACTIVE})` },
            { key: 'SCHEDULED', label: `Scheduled (${counts.SCHEDULED})` },
            { key: 'CLOSED', label: `Closed (${counts.CLOSED})` },
            { key: 'FORCE_CLOSED', label: `Force Closed (${counts.FORCE_CLOSED})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setStatusFilter(tab.key)}
              className={`px-2.5 py-1 uppercase tracking-wider transition-colors border rounded-none whitespace-nowrap text-[11px] ${
                statusFilter === tab.key
                  ? 'bg-meridian-ink text-meridian-ivory border-meridian-ink font-bold'
                  : 'bg-meridian-surface text-meridian-muted border-meridian-line hover:text-meridian-ink hover:bg-meridian-surfaceDeep'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right: Closing Soon Toggle, Search, Local/UTC Switch */}
        <div className="flex items-center gap-3 shrink-0 ml-auto flex-wrap sm:flex-nowrap">
          
          {/* Custom square toggle for Closing Soon (1px Graphite border, lime fill when on, focus ring) */}
          <button
            type="button"
            role="checkbox"
            aria-checked={closingSoonOnly}
            onClick={() => setClosingSoonOnly(!closingSoonOnly)}
            className="flex items-center gap-2 select-none group focus:outline-none focus-visible:ring-1 focus-visible:ring-meridian-ink cursor-pointer"
          >
            <div
              className={`w-4 h-4 rounded-[2px] border border-meridian-graphite flex items-center justify-center transition-colors ${
                closingSoonOnly ? 'bg-meridian-lime text-meridian-graphite' : 'bg-transparent'
              }`}
            >
              {closingSoonOnly && <Check className="w-3 h-3 stroke-[3]" />}
            </div>
            <span className={`text-[11px] font-mono uppercase whitespace-nowrap ${
              closingSoonOnly ? 'font-bold text-meridian-orange' : 'text-meridian-muted group-hover:text-meridian-ink'
            }`}>
              Closing Soon (&lt;15m)
            </span>
          </button>

          {/* Supplier-only My Bids filter */}
          {!isBuyer && (
            <button
              type="button"
              role="checkbox"
              aria-checked={myBidsOnly}
              onClick={() => setMyBidsOnly(!myBidsOnly)}
              className="flex items-center gap-2 select-none group border-l border-meridian-line pl-3 focus:outline-none focus-visible:ring-1 focus-visible:ring-meridian-ink cursor-pointer"
            >
              <div
                className={`w-4 h-4 rounded-[2px] border border-meridian-graphite flex items-center justify-center transition-colors ${
                  myBidsOnly ? 'bg-meridian-lime text-meridian-graphite' : 'bg-transparent'
                }`}
              >
                {myBidsOnly && <Check className="w-3 h-3 stroke-[3]" />}
              </div>
              <span className={`text-[11px] font-mono uppercase whitespace-nowrap ${
                myBidsOnly ? 'font-bold text-meridian-ink' : 'text-meridian-muted group-hover:text-meridian-ink'
              }`}>
                My Bids Only
              </span>
            </button>
          )}

          {/* Search Field with explicit min-w-[280px] */}
          <div className="relative min-w-[280px]">
            <Search className="w-3.5 h-3.5 text-meridian-muted absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search RFQ, port or carrier"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-meridian-surface border border-meridian-line pl-8 pr-3 py-1 text-xs font-mono text-meridian-ink focus:border-meridian-ink outline-none"
            />
          </div>

          {/* Local / UTC Toggle */}
          <div className="flex items-center font-mono text-xs border border-meridian-line bg-meridian-surfaceDeep shrink-0">
            <button
              type="button"
              onClick={() => handleTimezoneChange(false)}
              className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors ${
                !isUtc ? 'bg-meridian-ink text-meridian-ivory' : 'text-meridian-muted hover:text-meridian-ink'
              }`}
            >
              Local
            </button>
            <span className="text-meridian-muted/40 text-[10px]">|</span>
            <button
              type="button"
              onClick={() => handleTimezoneChange(true)}
              className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors ${
                isUtc ? 'bg-meridian-ink text-meridian-ivory' : 'text-meridian-muted hover:text-meridian-ink'
              }`}
            >
              UTC
            </button>
          </div>
        </div>
      </div>

      {/* 3. Main Auction Table (Fixed Layout, 6 Columns, No Overflow) */}
      <div className="border border-meridian-line bg-meridian-surface overflow-x-clip md:overflow-x-clip shadow-sm scroll-mt-[90px] scroll-pt-[90px]">
        
        {/* Error State */}
        {error ? (
          <div className="p-8 text-center font-mono">
            <AlertTriangle className="w-8 h-8 text-meridian-orange mx-auto mb-2" />
            <div className="text-sm font-bold text-meridian-ink">{error}</div>
            <button onClick={fetchRfqs} className="btn-secondary mt-3 px-4 py-1.5 text-xs font-mono">
              Retry
            </button>
          </div>
        ) : isLoading ? (
          /* Skeleton Loader (5 matching rows) */
          <div className="p-4 space-y-3 font-mono">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-[72px] bg-meridian-surfaceDeep/60 animate-pulse border border-meridian-line/40" />
            ))}
          </div>
        ) : displayedRfqs.length === 0 ? (
          /* Empty State */
          <div className="py-16 text-center font-mono text-xs text-meridian-muted space-y-3">
            <FilterX className="w-8 h-8 mx-auto text-meridian-muted opacity-60" />
            <div className="text-sm font-medium text-meridian-ink">No auctions match these filters</div>
            <p className="text-xs text-meridian-muted">Try adjusting your status tab, search query, or urgency toggles.</p>
            <button
              onClick={clearAllFilters}
              className="btn-secondary px-3 py-1.5 text-xs uppercase tracking-wider inline-flex items-center gap-1.5"
            >
              Clear Filters
            </button>
          </div>
        ) : (
          <>
            {/* Desktop / Tablet Table View (hidden on mobile < 768px) */}
            <table className="hidden md:table w-full text-left font-mono text-xs border-collapse table-fixed">
              {/* Explicit Column Width Allocations: RFQ 34%, Lowest Bid 12%, Current Close 17%, Forced Close 15%, Status 9%, Action 13% */}
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '15%' }} />
                <col style={{ width: '9%' }} />
                <col style={{ width: '13%' }} />
              </colgroup>

              {/* Opaque Sticky Header at nav height (48px) with 1px bottom rule */}
              <thead className="text-meridian-muted text-[11px] font-mono uppercase tracking-[0.08em]">
                <tr>
                  <th 
                    style={{ position: 'sticky', top: 48, background: '#E9E6DA', zIndex: 5 }}
                    className="py-3 px-4 cursor-pointer hover:text-meridian-ink select-none border-b border-meridian-line"
                    onClick={() => handleSort('reference_id')}
                    aria-sort={sortField === 'reference_id' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>RFQ / Corridor</span>
                      {getSortIcon('reference_id')}
                    </div>
                  </th>

                  <th 
                    style={{ position: 'sticky', top: 48, background: '#E9E6DA', zIndex: 5 }}
                    className="py-3 px-4 cursor-pointer hover:text-meridian-ink select-none border-b border-meridian-line"
                    onClick={() => handleSort('lowest_bid_total')}
                    aria-sort={sortField === 'lowest_bid_total' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Lowest Bid (L1)</span>
                      {getSortIcon('lowest_bid_total')}
                    </div>
                  </th>

                  <th 
                    style={{ position: 'sticky', top: 48, background: '#E9E6DA', zIndex: 5 }}
                    className="py-3 px-4 cursor-pointer hover:text-meridian-ink select-none border-b border-meridian-line"
                    onClick={() => handleSort('effective_close')}
                    aria-sort={sortField === 'effective_close' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Current Close</span>
                      {getSortIcon('effective_close')}
                    </div>
                  </th>

                  <th 
                    style={{ position: 'sticky', top: 48, background: '#E9E6DA', zIndex: 5 }}
                    className="py-3 px-4 cursor-pointer hover:text-meridian-ink select-none border-b border-meridian-line"
                    onClick={() => handleSort('forced_close')}
                    aria-sort={sortField === 'forced_close' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Forced Close</span>
                      {getSortIcon('forced_close')}
                    </div>
                  </th>

                  <th 
                    style={{ position: 'sticky', top: 48, background: '#E9E6DA', zIndex: 5 }}
                    className="py-3 px-4 cursor-pointer hover:text-meridian-ink select-none border-b border-meridian-line"
                    onClick={() => handleSort('status')}
                    aria-sort={sortField === 'status' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Status</span>
                      {getSortIcon('status')}
                    </div>
                  </th>

                  <th 
                    style={{ position: 'sticky', top: 48, background: '#E9E6DA', zIndex: 5 }}
                    className="py-3 px-4 text-right border-b border-meridian-line"
                  >
                    Action
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-meridian-line">
                {displayedRfqs.map((rfq) => {
                  const isActive = rfq.status === 'ACTIVE';
                  const isScheduled = rfq.status === 'SCHEDULED';
                  const closeMs = new Date(rfq.effective_close).getTime();
                  const diffMs = closeMs - Date.now();
                  const isClosingSoon = isActive && diffMs > 0 && diffMs <= 15 * 60 * 1000;
                  const locodeOrigin = extractLocode(rfq.origin);
                  const locodeDest = extractLocode(rfq.destination);

                  // Formatted date parts
                  const closeParts = formatAuctionDateParts(rfq.effective_close, isUtc);
                  const forcedParts = formatAuctionDateParts(rfq.forced_close, isUtc);

                  // Extension count tag
                  const extCount = rfq.recent_extensions?.length || 0;
                  const extMin = rfq.config?.extension_minutes || 5;

                  return (
                    <tr
                      key={rfq.id}
                      onClick={() => navigate(`/auctions/${rfq.id}`)}
                      className="h-[72px] max-h-[72px] hover:bg-meridian-surfaceDeep/70 transition-colors cursor-pointer select-none"
                    >
                      {/* Column 1: RFQ (34%) - Ref in mono, title clamped 2 lines with tooltip, route SGSIN -> AUMEL */}
                      <td 
                        className="px-4 py-0 align-middle font-mono"
                        style={isClosingSoon ? { boxShadow: 'inset 3px 0 0 #E4774D' } : undefined}
                      >
                        <div className="font-bold text-meridian-ink text-xs leading-none">
                          {rfq.reference_id}
                        </div>
                        <div 
                          className="font-sans text-xs text-meridian-ink font-medium mt-1 line-clamp-2 leading-tight"
                          title={rfq.title}
                        >
                          {rfq.title}
                        </div>
                        <div 
                          className="text-[11px] font-mono text-meridian-muted flex items-center gap-1 mt-1 truncate"
                          title={`${rfq.origin} → ${rfq.destination}`}
                        >
                          <span className="font-semibold text-meridian-ink">{locodeOrigin}</span>
                          <ArrowRight className="w-3 h-3 text-meridian-muted shrink-0" />
                          <span className="font-semibold text-meridian-ink">{locodeDest}</span>
                        </div>
                      </td>

                      {/* Column 2: Lowest Bid L1 (12%) - Formatted price with bids count & carriers */}
                      <td className="px-4 py-0 align-middle font-mono tabular-nums">
                        {rfq.lowest_bid_total ? (
                          <div className="font-bold text-sm text-meridian-ink leading-tight">
                            ${Number(rfq.lowest_bid_total).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                          </div>
                        ) : (
                          <span className="text-meridian-muted leading-tight">—</span>
                        )}
                        <div className="text-[11px] text-meridian-muted mt-1 truncate">
                          {rfq.total_bids_count} bids · {rfq.participating_suppliers_count} carriers
                        </div>
                      </td>

                      {/* Column 3: Current Close (17%) - Line 1: date + tz, Line 2: live countdown */}
                      <td className="px-4 py-0 align-middle font-mono tabular-nums">
                        <div className="flex items-baseline whitespace-nowrap leading-tight">
                          <span className="text-xs font-medium text-meridian-ink">{closeParts.datePart}</span>
                          <span className="ml-1 text-[10px] text-meridian-muted font-mono whitespace-nowrap">{closeParts.tzPart}</span>
                        </div>

                        {isActive ? (
                          <div className="flex items-center gap-1.5 mt-1 whitespace-nowrap">
                            <span className={isClosingSoon ? 'text-meridian-orange font-bold text-xs' : 'text-meridian-muted text-xs'}>
                              <CountdownTimer targetDate={rfq.effective_close} size="sm" theme="light" /> left
                            </span>
                            {extCount > 0 && (
                              <span className="px-1 py-0.2 bg-meridian-surfaceDeep text-meridian-ink border border-meridian-line text-[10px] font-bold">
                                +{extMin}m ×{extCount}
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="text-[10px] text-meridian-muted mt-1 whitespace-nowrap">
                            {isScheduled ? 'Scheduled Start' : 'Concluded'}
                          </div>
                        )}
                      </td>

                      {/* Column 4: Forced Close (15%) - Full-contrast ink in same weight as Current Close */}
                      <td className="px-4 py-0 align-middle font-mono tabular-nums">
                        <div className="flex items-baseline whitespace-nowrap leading-tight">
                          <span className="text-xs font-medium text-meridian-ink">{forcedParts.datePart}</span>
                          <span className="ml-1 text-[10px] text-meridian-muted font-mono whitespace-nowrap">{forcedParts.tzPart}</span>
                        </div>
                        <div className="text-[10px] text-meridian-muted mt-1 uppercase tracking-wider">
                          Hard Stop
                        </div>
                      </td>

                      {/* Column 5: Status (9%) - Plain text + lime dot for Active (no chip), filled chips for others */}
                      <td className="px-4 py-0 align-middle font-mono">
                        {isActive ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-meridian-ink">
                            <span className="w-2 h-2 rounded-full bg-meridian-lime border border-meridian-ink/30 shrink-0" />
                            <span>Active</span>
                          </span>
                        ) : (
                          <StatusChip status={rfq.status} size="compact" />
                        )}
                      </td>

                      {/* Column 6: Action (13%) - Right-aligned, always visible, Enter Room is only lime element */}
                      <td className="px-4 py-0 align-middle text-right">
                        <div className="flex items-center justify-end" onClick={(e) => e.stopPropagation()}>
                          {isActive ? (
                            <button
                              onClick={() => navigate(`/live/${rfq.id}`)}
                              className="btn-primary px-3 py-1.5 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5 shrink-0"
                            >
                              <Radio className="w-3 h-3" />
                              <span>Enter Room</span>
                            </button>
                          ) : isScheduled ? (
                            <button
                              onClick={() => navigate(`/auctions/${rfq.id}`)}
                              className="btn-secondary px-3 py-1.5 text-xs font-mono uppercase tracking-wider shrink-0"
                            >
                              View
                            </button>
                          ) : (
                            <button
                              onClick={() => navigate(`/auctions/${rfq.id}`)}
                              className="btn-secondary px-3 py-1.5 text-xs font-mono uppercase tracking-wider flex items-center gap-1 shrink-0"
                            >
                              <FileText className="w-3 h-3" />
                              <span>History</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Mobile Stacked Card View (< 768px) */}
            <div className="md:hidden divide-y divide-meridian-line font-mono text-xs">
              {displayedRfqs.map((rfq) => {
                const isActive = rfq.status === 'ACTIVE';
                const isScheduled = rfq.status === 'SCHEDULED';
                const closeMs = new Date(rfq.effective_close).getTime();
                const diffMs = closeMs - Date.now();
                const isClosingSoon = isActive && diffMs > 0 && diffMs <= 15 * 60 * 1000;
                const locodeOrigin = extractLocode(rfq.origin);
                const locodeDest = extractLocode(rfq.destination);

                const closeParts = formatAuctionDateParts(rfq.effective_close, isUtc);
                const forcedParts = formatAuctionDateParts(rfq.forced_close, isUtc);

                return (
                  <div
                    key={rfq.id}
                    onClick={() => navigate(`/auctions/${rfq.id}`)}
                    className="p-4 space-y-2.5 hover:bg-meridian-surfaceDeep transition-colors cursor-pointer select-none"
                    style={isClosingSoon ? { boxShadow: 'inset 3px 0 0 #E4774D' } : undefined}
                  >
                    {/* Line 1: Reference in mono + Status */}
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-meridian-ink">{rfq.reference_id}</span>
                      {isActive ? (
                        <span className="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-meridian-ink">
                          <span className="w-2 h-2 rounded-full bg-meridian-lime border border-meridian-ink/30 shrink-0" />
                          <span>Active</span>
                        </span>
                      ) : (
                        <StatusChip status={rfq.status} size="compact" />
                      )}
                    </div>

                    {/* Line 2: Title (2 lines) and Route */}
                    <div>
                      <div className="font-sans text-xs font-medium text-meridian-ink line-clamp-2" title={rfq.title}>
                        {rfq.title}
                      </div>
                      <div className="text-[11px] font-mono text-meridian-muted flex items-center gap-1 mt-1">
                        <span className="font-semibold text-meridian-ink">{locodeOrigin}</span>
                        <ArrowRight className="w-3 h-3 text-meridian-muted shrink-0" />
                        <span className="font-semibold text-meridian-ink">{locodeDest}</span>
                      </div>
                    </div>

                    {/* Line 3: L1 Price, Current Close, and Forced Close (Hard Stop) */}
                    <div className="grid grid-cols-3 gap-2 pt-1 border-t border-meridian-line text-xs">
                      <div>
                        <span className="text-[10px] text-meridian-muted uppercase block">Lowest (L1):</span>
                        <span className="font-bold text-xs text-meridian-ink tabular-nums">
                          {rfq.lowest_bid_total ? `$${Number(rfq.lowest_bid_total).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-meridian-muted uppercase block">Current:</span>
                        {isActive ? (
                          <span className={isClosingSoon ? 'text-meridian-orange font-bold text-xs' : 'text-meridian-ink text-xs'}>
                            <CountdownTimer targetDate={rfq.effective_close} size="sm" theme="light" />
                          </span>
                        ) : (
                          <span className="text-meridian-muted text-xs">{isScheduled ? 'Scheduled' : 'Concluded'}</span>
                        )}
                      </div>
                      <div>
                        <span className="text-[10px] text-meridian-muted uppercase block">Hard Stop:</span>
                        <span className="font-mono text-xs font-medium text-meridian-ink tabular-nums">
                          {forcedParts.datePart}
                        </span>
                      </div>
                    </div>

                    {/* Line 4: Action Button */}
                    <div className="pt-2" onClick={(e) => e.stopPropagation()}>
                      {isActive ? (
                        <button
                          onClick={() => navigate(`/live/${rfq.id}`)}
                          className="btn-primary w-full py-2 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-1.5"
                        >
                          <Radio className="w-3.5 h-3.5" />
                          <span>Enter Room</span>
                        </button>
                      ) : isScheduled ? (
                        <button
                          onClick={() => navigate(`/auctions/${rfq.id}`)}
                          className="btn-secondary w-full py-2 text-xs font-mono uppercase tracking-wider"
                        >
                          View RFQ
                        </button>
                      ) : (
                        <button
                          onClick={() => navigate(`/auctions/${rfq.id}`)}
                          className="btn-secondary w-full py-2 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-1.5"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>View History</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

    </div>
  );
};
