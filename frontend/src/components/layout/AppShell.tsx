import React from 'react';
import { Navbar } from './Navbar';
import { useWebSocket } from '../../context/WebSocketContext';
import { ShieldCheck } from 'lucide-react';

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isConnected, clockOffsetMs, getServerNow } = useWebSocket();
  const [serverTimeStr, setServerTimeStr] = React.useState<string>('');

  React.useEffect(() => {
    const timer = setInterval(() => {
      const now = getServerNow();
      setServerTimeStr(now.toUTCString().replace('GMT', 'UTC'));
    }, 1000);
    return () => clearInterval(timer);
  }, [getServerNow]);

  return (
    <div className="min-h-screen flex flex-col bg-meridian-bg text-meridian-ink selection:bg-meridian-lime selection:text-meridian-ink">
      {/* 1. Slim 48px Dark Top Strip */}
      <Navbar />

      {/* 2. Main Content Canvas (~70% Light Surfaces) */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* 3. Editorial Light Footer Bar */}
      <footer className="border-t border-meridian-line bg-meridian-surfaceDeep text-[11px] font-mono text-meridian-muted py-2.5 px-4 sm:px-8">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-meridian-ink font-medium">
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-meridian-ink' : 'bg-meridian-orange'}`} />
              WS Engine: {isConnected ? 'Synchronized' : 'Reconnecting...'}
            </span>
            <span className="hidden sm:inline border-l border-meridian-line pl-4 text-meridian-ink">
              Drift: <span className="font-semibold tabular-nums">{clockOffsetMs > 0 ? `+${clockOffsetMs}` : clockOffsetMs}ms</span>
            </span>
            <span className="hidden md:inline border-l border-meridian-line pl-4 text-meridian-ink">
              Server UTC: <span className="tabular-nums font-semibold">{serverTimeStr || 'Syncing...'}</span>
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-meridian-ink">
              <ShieldCheck className="w-3.5 h-3.5 text-meridian-ink" />
              ACID Row-Locked
            </span>
            <span className="text-meridian-muted">MERIDIAN v1.0.0</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
