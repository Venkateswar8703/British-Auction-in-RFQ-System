import React from 'react';
import { RFQStatus } from '../../types';

interface BadgeProps {
  status?: RFQStatus | string;
  variant?: 'status' | 'rank' | 'trigger' | 'neutral';
  size?: 'sm' | 'md' | 'lg';
  children?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  status,
  variant = 'status',
  size = 'md',
  children,
}) => {
  const sizeClasses = {
    sm: 'text-[10px] px-1.5 py-0.5 tracking-wider',
    md: 'text-xs px-2 py-0.5 tracking-wide',
    lg: 'text-sm px-3 py-1 font-semibold tracking-wide',
  }[size];

  if (variant === 'status' && status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return (
          <span className={`inline-flex items-center gap-1.5 font-mono uppercase bg-meridian-lime text-meridian-ink border border-meridian-ink rounded-none ${sizeClasses}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-meridian-ink beacon-pulse" />
            ACTIVE
          </span>
        );
      case 'SCHEDULED':
        return (
          <span className={`inline-flex items-center gap-1.5 font-mono uppercase bg-meridian-surfaceDeep text-meridian-muted border border-meridian-line rounded-none ${sizeClasses}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-meridian-muted" />
            SCHEDULED
          </span>
        );
      case 'CLOSED':
        return (
          <span className={`inline-flex items-center gap-1.5 font-mono uppercase bg-transparent text-meridian-ink border border-meridian-ink rounded-none ${sizeClasses}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-meridian-ink" />
            CLOSED
          </span>
        );
      case 'FORCE_CLOSED':
        return (
          <span className={`inline-flex items-center gap-1.5 font-mono uppercase bg-meridian-orange text-meridian-ink font-semibold border border-meridian-ink rounded-none ${sizeClasses}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-meridian-ink" />
            FORCE CLOSED
          </span>
        );
      default:
        return (
          <span className={`inline-flex items-center font-mono uppercase bg-meridian-surfaceDeep text-meridian-ink border border-meridian-line rounded-none ${sizeClasses}`}>
            {status}
          </span>
        );
    }
  }

  if (variant === 'rank') {
    const isL1 = children === 'L1';
    return (
      <span className={`inline-flex items-center font-mono font-bold rounded-none ${sizeClasses} ${
        isL1
          ? 'bg-meridian-lime text-meridian-ink border border-meridian-ink'
          : 'bg-meridian-surfaceDeep text-meridian-ink border border-meridian-line'
      }`}>
        {children}
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center font-mono text-xs uppercase bg-meridian-surfaceDeep text-meridian-ink border border-meridian-line rounded-none ${sizeClasses}`}>
      {children || status}
    </span>
  );
};
