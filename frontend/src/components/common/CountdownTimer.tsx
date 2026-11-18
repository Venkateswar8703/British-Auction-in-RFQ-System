import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../context/WebSocketContext';

interface CountdownTimerProps {
  targetDate: string;
  startDate?: string;
  triggerWindowMinutes?: number;
  forcedCloseDate?: string;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  theme?: 'light' | 'dark';
  onExpire?: () => void;
}

export const CountdownTimer: React.FC<CountdownTimerProps> = ({
  targetDate,
  startDate,
  triggerWindowMinutes = 10,
  forcedCloseDate,
  size = 'md',
  theme = 'light',
  onExpire,
}) => {
  const { getServerNow } = useWebSocket();
  const [timeLeftMs, setTimeLeftMs] = useState<number>(0);
  const [isInsideTrigger, setIsInsideTrigger] = useState<boolean>(false);
  const [isExpired, setIsExpired] = useState<boolean>(false);

  useEffect(() => {
    let animId: number;

    const tick = () => {
      const now = getServerNow();
      const target = new Date(targetDate).getTime();
      const diff = target - now.getTime();

      if (diff <= 0) {
        setTimeLeftMs(0);
        setIsExpired(true);
        if (!isExpired && onExpire) {
          onExpire();
        }
      } else {
        setTimeLeftMs(diff);
        setIsExpired(false);
        const windowMs = triggerWindowMinutes * 60 * 1000;
        setIsInsideTrigger(diff <= windowMs);
      }
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [targetDate, triggerWindowMinutes, getServerNow, onExpire, isExpired]);

  // Format time
  const hours = Math.floor(timeLeftMs / (1000 * 60 * 60));
  const minutes = Math.floor((timeLeftMs % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((timeLeftMs % (1000 * 60)) / 1000);
  const tenths = Math.floor((timeLeftMs % 1000) / 100);

  const pad = (n: number) => n.toString().padStart(2, '0');

  // Text colors based on theme and urgency
  const normalColor = theme === 'dark' ? 'text-meridian-ivory' : 'text-meridian-ink';
  const subColor = theme === 'dark' ? 'text-meridian-muted' : 'text-meridian-muted';
  const triggerColor = 'text-meridian-orange';

  if (isExpired) {
    return (
      <div className="font-mono text-meridian-muted font-semibold tracking-wider uppercase text-xs md:text-sm">
        00:00:00 [CONCLUDED]
      </div>
    );
  }

  if (size === 'hero') {
    return (
      <div className="flex flex-col">
        <div className="flex items-baseline gap-1 font-mono tabular-nums font-semibold tracking-tight">
          <span className={`text-4xl sm:text-5xl lg:text-6xl ${isInsideTrigger ? triggerColor : normalColor}`}>
            {hours > 0 && `${pad(hours)}:`}
            {pad(minutes)}:{pad(seconds)}
          </span>
          <span className={`text-xl sm:text-2xl ${isInsideTrigger ? triggerColor : subColor}`}>
            .{tenths}s
          </span>
        </div>
        {isInsideTrigger && (
          <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 bg-meridian-orange/20 border border-meridian-orange text-meridian-orange text-xs font-mono font-medium uppercase tracking-wider w-fit">
            <span className="w-1.5 h-1.5 rounded-full bg-meridian-orange beacon-pulse" />
            Trigger Window Active ({triggerWindowMinutes}m)
          </div>
        )}
      </div>
    );
  }

  if (size === 'lg') {
    return (
      <div className={`font-mono tabular-nums font-bold text-xl sm:text-2xl ${isInsideTrigger ? triggerColor : normalColor}`}>
        {hours > 0 && `${pad(hours)}:`}
        {pad(minutes)}:{pad(seconds)}
      </div>
    );
  }

  return (
    <span className={`font-mono tabular-nums font-medium ${isInsideTrigger ? triggerColor : normalColor}`}>
      {hours > 0 && `${pad(hours)}:`}
      {pad(minutes)}:{pad(seconds)}
    </span>
  );
};
