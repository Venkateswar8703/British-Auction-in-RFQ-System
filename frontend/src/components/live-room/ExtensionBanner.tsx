import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, AlertTriangle, Zap, X } from 'lucide-react';
import { format } from 'date-fns';

interface ExtensionBannerProps {
  extensionNotice: {
    type: 'EXTENSION_APPLIED' | 'EXTENSION_CAPPED' | 'DEMO_RESEEDED';
    previousClose?: string;
    newClose?: string;
    reason: string;
    isClamped?: boolean;
    timestamp: Date;
  } | null;
  onDismiss?: () => void;
}

export const ExtensionBanner: React.FC<ExtensionBannerProps> = ({
  extensionNotice,
  onDismiss,
}) => {
  if (!extensionNotice) return null;

  const isCapped = extensionNotice.type === 'EXTENSION_CAPPED';
  const isReseed = extensionNotice.type === 'DEMO_RESEEDED';

  // Calculate delta minutes if available
  let deltaStr = '+3:00';
  if (extensionNotice.previousClose && extensionNotice.newClose) {
    const diffMs = new Date(extensionNotice.newClose).getTime() - new Date(extensionNotice.previousClose).getTime();
    const diffMin = Math.round(diffMs / 60000);
    if (diffMin > 0) {
      deltaStr = `+${diffMin}:00`;
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.18 }}
        className={`w-full p-3 border font-mono text-xs rounded-none mb-4 ${
          isCapped
            ? 'bg-meridian-orange text-meridian-ink border-meridian-ink font-semibold'
            : isReseed
            ? 'bg-meridian-lime text-meridian-ink border-meridian-ink font-medium'
            : 'bg-meridian-orange text-meridian-ink border-meridian-ink font-medium'
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            {isCapped ? (
              <AlertTriangle className="w-4 h-4 shrink-0 text-meridian-ink" />
            ) : isReseed ? (
              <Zap className="w-4 h-4 shrink-0 text-meridian-ink" />
            ) : (
              <Clock className="w-4 h-4 shrink-0 text-meridian-ink" />
            )}
            <div>
              <div className="font-bold uppercase tracking-wider text-[11px] flex items-center gap-2">
                <span>
                  {isCapped
                    ? 'EXTENSION CAPPED AT FORCED CLOSE'
                    : isReseed
                    ? 'LIVE DEMO TIMELINE RE-INITIALIZED'
                    : 'TRIGGER EXTENSION APPLIED'}
                </span>
                {!isCapped && !isReseed && (
                  <span className="bg-meridian-ink text-meridian-orange px-1.5 py-0.2 font-mono text-xs font-bold">
                    {deltaStr}
                  </span>
                )}
                {extensionNotice.isClamped && (
                  <span className="bg-meridian-ink text-meridian-ivory px-1 py-0.2 text-[9px] uppercase">
                    Clamped
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-xs text-meridian-ink leading-tight font-sans">
                {extensionNotice.reason}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {extensionNotice.newClose && (
              <div className="hidden sm:block text-right">
                <span className="text-[10px] uppercase opacity-80 block">New Effective Close</span>
                <span className="font-bold text-xs tabular-nums">
                  {format(new Date(extensionNotice.newClose), 'HH:mm:ss')} UTC
                </span>
              </div>
            )}
            {onDismiss && (
              <button
                onClick={onDismiss}
                className="p-1 hover:bg-black/10 transition-colors"
                title="Dismiss banner"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};
