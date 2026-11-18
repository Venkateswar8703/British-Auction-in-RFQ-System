import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { RFQ, Bid, SupplierRank, WebSocketAuctionPayload } from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import { ShipmentSpecsPanel } from '../components/live-room/ShipmentSpecsPanel';
import { BidSubmissionPanel } from '../components/live-room/BidSubmissionPanel';
import { RankLadder } from '../components/live-room/RankLadder';
import { ExtensionBanner } from '../components/live-room/ExtensionBanner';
import { LiveActivityFeed, FeedItem } from '../components/live-room/LiveActivityFeed';
import { CountdownTimer } from '../components/common/CountdownTimer';
import { InstrumentPanel } from '../components/common/Primitives';
import { AlertTriangle, ArrowLeft, RefreshCw, Zap } from 'lucide-react';
import { format } from 'date-fns';

export const LiveAuctionRoom: React.FC = () => {
  const { rfqId } = useParams<{ rfqId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { subscribeRfq } = useWebSocket();

  const [rfq, setRfq] = useState<RFQ | null>(null);
  const [rankings, setRankings] = useState<SupplierRank[]>([]);
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [extensionNotice, setExtensionNotice] = useState<any | null>(null);
  const [flashSupplierId, setFlashSupplierId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load RFQ data
  const loadRfqData = useCallback(async () => {
    try {
      let targetId = rfqId;
      if (!targetId || targetId === 'demo') {
        const demoList = await api.listRfqs({ search: 'LIVE-DEMO' });
        if (demoList.length > 0) {
          targetId = demoList[0].id;
        } else {
          const activeList = await api.listRfqs({ status: 'ACTIVE' });
          if (activeList.length > 0) {
            targetId = activeList[0].id;
          } else {
            setError('No active auctions found. Please seed the database.');
            setIsLoading(false);
            return;
          }
        }
      }

      const data = await api.getRfq(targetId!);
      setRfq(data);
      setRankings(data.rankings || []);

      const initialItems: FeedItem[] = [];
      if (data.recent_extensions) {
        data.recent_extensions.slice(0, 3).forEach((ext) => {
          initialItems.push({
            id: ext.id,
            type: 'EXTENSION_APPLIED',
            message: ext.reason,
            timestamp: ext.created_at,
          });
        });
      }
      setFeedItems(initialItems);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load auction room.');
      setIsLoading(false);
    }
  }, [rfqId]);

  useEffect(() => {
    loadRfqData();
  }, [loadRfqData]);

  // WebSocket Subscription for Live Room
  useEffect(() => {
    if (!rfq?.id) return;

    const unsubscribe = subscribeRfq(rfq.id, (payload: WebSocketAuctionPayload) => {
      const { event_type, data, server_time } = payload;

      if (event_type === 'NEW_BID') {
        setRfq((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            effective_close: data.effective_close || prev.effective_close,
            forced_close: data.forced_close || prev.forced_close,
            lowest_bid_total: data.rankings?.[0]?.total || prev.lowest_bid_total,
          };
        });

        setFlashSupplierId(data.supplier_id);
        setTimeout(() => setFlashSupplierId(null), 1000);

        if (data.rankings) {
          setRankings(data.rankings);
        }

        const newFeedItem: FeedItem = {
          id: `bid-${Date.now()}`,
          type: data.rank === 1 ? 'L1_CHANGED' : 'BID_SUBMITTED',
          message: `${data.supplier_name || 'Carrier'} submitted $${Number(data.total).toFixed(2)} [L${data.rank || 1}]`,
          timestamp: server_time,
          details: `${data.carrier_name} • ${data.transit_time_days} days`,
        };
        setFeedItems((prev) => [newFeedItem, ...prev.slice(0, 25)]);

        if (data.extension_applied && data.extension_details) {
          setExtensionNotice({
            type: 'EXTENSION_APPLIED',
            previousClose: data.extension_details.previous_close,
            newClose: data.extension_details.new_close,
            reason: data.extension_details.reason,
            isClamped: data.extension_details.is_clamped,
            timestamp: new Date(server_time),
          });
        } else if (data.extension_capped) {
          setExtensionNotice({
            type: 'EXTENSION_CAPPED',
            reason: 'Auction extension capped at forced close deadline limit.',
            timestamp: new Date(server_time),
          });
        }
      } else if (event_type === 'EXTENSION_APPLIED') {
        setRfq((prev) => (prev ? { ...prev, effective_close: data.new_close } : prev));
        setExtensionNotice({
          type: 'EXTENSION_APPLIED',
          previousClose: data.previous_close,
          newClose: data.new_close,
          reason: data.reason,
          isClamped: data.is_clamped,
          timestamp: new Date(server_time),
        });
      } else if (event_type === 'AUCTION_CLOSED' || event_type === 'FORCED_CLOSE') {
        setRfq((prev) => (prev ? { ...prev, status: data.status } : prev));
        const closeItem: FeedItem = {
          id: `close-${Date.now()}`,
          type: event_type,
          message: `Auction concluded: ${data.status}`,
          timestamp: server_time,
          details: data.reason,
        };
        setFeedItems((prev) => [closeItem, ...prev]);
      } else if (event_type === 'DEMO_RESEEDED') {
        setRfq((prev) => (prev ? { ...prev, effective_close: data.effective_close, status: 'ACTIVE' } : prev));
        setExtensionNotice({
          type: 'DEMO_RESEEDED',
          reason: 'Live demo auction timer was reset into active trigger window (~2.5m remaining).',
          newClose: data.effective_close,
          timestamp: new Date(server_time),
        });
      } else if (event_type === 'RECONNECTED') {
        // Full state resync after socket connection drop
        if (rfqId) {
          api.getRfq(rfqId).then((fullRfq) => {
            setRfq(fullRfq);
            if (fullRfq.rankings) setRankings(fullRfq.rankings);
          }).catch(() => {});
          api.listBids(rfqId).then((bidsData) => {
            setBids(bidsData);
          }).catch(() => {});
        }
      }
    });

    return () => unsubscribe();
  }, [rfq?.id, subscribeRfq]);

  // Reseed Live Demo Trigger
  const handleReseedLiveDemo = async () => {
    if (!rfq) return;
    try {
      await api.reseedDemoRfq(rfq.id);
      loadRfqData();
    } catch (err: any) {
      alert(`Could not reset demo: ${err.message}`);
    }
  };

  const handleBidSuccess = (newBid: Bid) => {
    loadRfqData();
  };

  if (isLoading) {
    return (
      <div className="py-24 text-center font-mono text-sm text-meridian-muted flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-meridian-ink" />
        Connecting to Meridian Live Trading Terminal...
      </div>
    );
  }

  if (error || !rfq) {
    return (
      <div className="p-8 bg-meridian-surface border border-meridian-line text-center font-mono">
        <AlertTriangle className="w-8 h-8 text-meridian-orange mx-auto mb-3" />
        <div className="text-base text-meridian-ink font-bold">{error || 'Auction not found'}</div>
        <button
          onClick={() => navigate('/auctions')}
          className="btn-secondary mt-4 px-4 py-2 text-xs uppercase tracking-wider"
        >
          Return to Auction Directory
        </button>
      </div>
    );
  }

  const isBuyer = user?.role === 'buyer';
  const currentLowest = rankings.length > 0 ? Number(rankings[0].total) : (rfq.lowest_bid_total ? Number(rfq.lowest_bid_total) : null);

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Control Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-meridian-line font-mono text-xs">
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
          <span className="text-meridian-ink uppercase tracking-wider">Trading Floor</span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReseedLiveDemo}
            className="btn-secondary px-3 py-1 text-xs font-mono flex items-center gap-1.5"
            title="Reset timer to ~2.5m before close to demonstrate extensions"
          >
            <Zap className="w-3.5 h-3.5 text-meridian-ink" />
            Reseed Live Demo (2.5m)
          </button>
          <button
            onClick={loadRfqData}
            className="p-1 text-meridian-muted hover:text-meridian-ink transition-colors"
            title="Refresh state"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Dynamic Extension Notification Banner */}
      <ExtensionBanner
        extensionNotice={extensionNotice}
        onDismiss={() => setExtensionNotice(null)}
      />

      {/* Signature 3-Zone Control Room Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* ZONE 1 (Left 3 cols): Specifications & Submitted Quote */}
        <div className="lg:col-span-3">
          <ShipmentSpecsPanel
            rfq={rfq}
            myLatestBid={rfq.my_latest_bid}
            isSupplier={!isBuyer}
          />
        </div>

        {/* ZONE 2 (Center 5 cols): Dark Focal Instrument Panels + Light Bid Form */}
        <div className="lg:col-span-5 space-y-5">
          
          {/* DARK INSTRUMENT 1: Live Countdown Console */}
          <InstrumentPanel className="p-6 relative overflow-hidden">
            <div className="flex items-center justify-between text-xs font-mono uppercase tracking-[0.08em] mb-2 text-white/60">
              <span>Closing Countdown</span>
              <span className="text-[10px] text-meridian-lime flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-meridian-lime beacon-pulse" />
                Compensated
              </span>
            </div>

            {/* Millisecond Live Countdown Hero */}
            <CountdownTimer
              targetDate={rfq.effective_close}
              forcedCloseDate={rfq.forced_close}
              triggerWindowMinutes={rfq.config?.trigger_window_minutes || 10}
              size="hero"
              theme="dark"
              onExpire={() => setRfq((prev) => prev ? { ...prev, status: 'CLOSED' } : prev)}
            />
          </InstrumentPanel>

          {/* DARK INSTRUMENT 2: Current Lowest Bid (L1) Block */}
          <InstrumentPanel className="p-5 flex items-center justify-between">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-[0.08em] text-white/60 mb-1 flex items-center gap-2">
                <span>Current Lowest Bid</span>
                <span className="px-1.5 py-0.2 bg-meridian-lime text-meridian-ink font-bold text-[10px]">
                  L1
                </span>
              </div>
              <div className="text-3xl sm:text-4xl font-mono font-bold text-white tabular-nums">
                {currentLowest ? `$${currentLowest.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : 'No Bids'}
              </div>
              {rankings.length > 0 && (
                <div className="text-xs font-mono text-white/70 mt-1">
                  Held by <span className="font-semibold text-white">{rankings[0].supplier_name}</span>
                </div>
              )}
            </div>

            <div className="text-right border-l border-white/15 pl-5">
              <span className="text-[10px] font-mono text-white/60 uppercase block">
                Effective Close
              </span>
              <span className="text-base font-mono font-bold text-white tabular-nums block">
                {format(new Date(rfq.effective_close), 'HH:mm:ss')} UTC
              </span>
              <span className="text-[10px] font-mono text-meridian-orange block mt-1">
                Forced: {format(new Date(rfq.forced_close), 'HH:mm:ss')}
              </span>
            </div>
          </InstrumentPanel>

          {/* Light Bid Submission Form (or Buyer Observation Console) */}
          <BidSubmissionPanel
            rfq={rfq}
            currentLowestBid={currentLowest}
            myLatestBid={rfq.my_latest_bid}
            isBuyer={isBuyer}
            onBidSuccess={handleBidSuccess}
          />
        </div>

        {/* ZONE 3 (Right 4 cols): Ranking Ladder & Activity Feed */}
        <div className="lg:col-span-4 space-y-5">
          <RankLadder
            rankings={rankings}
            currentSupplierId={user?.supplier_id}
            flashSupplierId={flashSupplierId}
          />

          <LiveActivityFeed items={feedItems} />
        </div>

      </div>
    </div>
  );
};
