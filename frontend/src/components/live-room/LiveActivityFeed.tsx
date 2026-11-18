import React from 'react';
import { format } from 'date-fns';
import { Activity } from 'lucide-react';

export interface FeedItem {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  details?: string;
}

interface LiveActivityFeedProps {
  items: FeedItem[];
}

export const LiveActivityFeed: React.FC<LiveActivityFeedProps> = ({ items }) => {
  return (
    <div className="bg-meridian-surface border border-meridian-line p-5 flex flex-col flex-1 text-meridian-ink">
      <div className="flex items-center justify-between pb-3 border-b border-meridian-line mb-3">
        <div className="text-xs font-mono font-bold uppercase text-meridian-ink tracking-wider flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-meridian-ink" />
          Live Audit Feed
        </div>
        <span className="text-[10px] font-mono text-meridian-muted uppercase flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-meridian-ink beacon-pulse" />
          Stream Active
        </span>
      </div>

      <div 
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        className="space-y-2 overflow-y-auto max-h-[240px] font-mono text-[11px] pr-1"
      >
        {items.length === 0 ? (
          <div className="py-8 text-center text-meridian-muted text-xs">
            Listening for live auction transmissions...
          </div>
        ) : (
          items.map((item) => {
            const isExtension = item.type.includes('EXTENSION');
            const isBid = item.type.includes('BID') || item.type.includes('L1');

            return (
              <div
                key={item.id}
                className="p-2.5 bg-meridian-surface border border-meridian-line hover:bg-meridian-surfaceDeep transition-colors flex items-start gap-2.5 leading-tight rounded-none"
              >
                {/* Square event marker */}
                <span
                  className={`w-2 h-2 shrink-0 mt-1 rounded-none ${
                    isBid
                      ? 'bg-meridian-lime border border-meridian-ink'
                      : isExtension
                      ? 'bg-meridian-orange border border-meridian-ink'
                      : 'bg-meridian-ink'
                  }`}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between text-[10px] text-meridian-muted mb-0.5">
                    <span className="uppercase font-bold text-meridian-ink">{item.type}</span>
                    <span className="tabular-nums">
                      {item.timestamp ? format(new Date(item.timestamp), 'HH:mm:ss') : ''}
                    </span>
                  </div>
                  <div className="text-meridian-ink text-xs font-sans">{item.message}</div>
                  {item.details && (
                    <div className="mt-0.5 text-[10px] text-meridian-muted font-mono">{item.details}</div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
