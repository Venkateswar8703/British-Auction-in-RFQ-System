import React from 'react';
import { SupplierRank } from '../../types';
import { Trophy } from 'lucide-react';

interface RankLadderProps {
  rankings: SupplierRank[];
  currentSupplierId?: string | null;
  flashSupplierId?: string | null;
}

export const RankLadder: React.FC<RankLadderProps> = ({
  rankings,
  currentSupplierId,
  flashSupplierId,
}) => {
  const l1Price = rankings.length > 0 ? Number(rankings[0].total) : 0;

  return (
    <div className="bg-meridian-surface border border-meridian-line p-5 flex flex-col text-meridian-ink">
      <div className="flex items-center justify-between pb-3 border-b border-meridian-line mb-4">
        <div className="text-xs font-mono font-bold uppercase text-meridian-ink tracking-wider flex items-center gap-2">
          <Trophy className="w-3.5 h-3.5 text-meridian-ink" />
          Ranking Ladder (L1 → Ln)
        </div>
        <span className="text-[11px] font-mono text-meridian-muted uppercase tracking-wider">
          {rankings.length} Competitors
        </span>
      </div>

      {rankings.length === 0 ? (
        <div className="py-12 text-center text-meridian-muted font-mono text-xs">
          No bids recorded yet. First valid submission captures L1.
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto max-h-[340px] pr-1">
          {rankings.map((r) => {
            const isL1 = r.rank === 1;
            const isCurrentSupplier = r.supplier_id === currentSupplierId;
            const isFlashing = r.supplier_id === flashSupplierId;
            const priceDiff = Number(r.total) - l1Price;

            return (
              <div
                key={r.supplier_id}
                className={`p-3 border transition-all text-xs font-mono flex items-center justify-between rounded-none ${
                  isFlashing ? 'rank-flash' : ''
                } ${
                  isL1
                    ? 'bg-meridian-lime border-meridian-ink text-meridian-ink shadow-sm'
                    : isCurrentSupplier
                    ? 'bg-meridian-surfaceDeep border-meridian-line border-l-4 border-l-meridian-ink text-meridian-ink'
                    : 'bg-meridian-surface border-meridian-line hover:bg-meridian-surfaceDeep text-meridian-ink'
                }`}
              >
                {/* Left: Rank & Supplier Name */}
                <div className="flex items-center gap-3">
                  <div
                    className={`w-6 h-6 flex items-center justify-center font-bold text-xs shrink-0 rounded-none ${
                      isL1
                        ? 'bg-meridian-ink text-meridian-lime'
                        : 'bg-meridian-surfaceDeep text-meridian-ink border border-meridian-line'
                    }`}
                  >
                    L{r.rank}
                  </div>
                  <div>
                    <div className="font-semibold text-meridian-ink flex items-center gap-1.5">
                      <span className="truncate max-w-[130px]">{r.supplier_name}</span>
                      {isCurrentSupplier && (
                        <span className="text-[9px] uppercase px-1.5 py-0.2 bg-meridian-ink text-meridian-ivory font-bold">
                          YOU
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-meridian-muted flex items-center gap-1.5 mt-0.5">
                      <span>{r.carrier_name}</span>
                      <span>•</span>
                      <span>{r.transit_time_days}d transit</span>
                    </div>
                  </div>
                </div>

                {/* Right: Total Price & Delta */}
                <div className="text-right">
                  <div className={`font-bold tabular-nums text-sm text-meridian-ink`}>
                    ${Number(r.total).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="text-[10px] tabular-nums mt-0.5">
                    {isL1 ? (
                      <span className="text-meridian-ink font-bold uppercase tracking-wider text-[9px]">
                        ★ LEADING
                      </span>
                    ) : (
                      <span className="text-meridian-muted font-medium">
                        +${priceDiff.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
