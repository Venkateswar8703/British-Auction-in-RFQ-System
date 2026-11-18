import React from 'react';

// 1. Panel (Light Container)
interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  variant?: 'surface' | 'deep' | 'ghost';
}

export const Panel: React.FC<PanelProps> = ({
  children,
  className = '',
  variant = 'surface',
  ...props
}) => {
  const bgClass =
    variant === 'surface'
      ? 'bg-meridian-surface'
      : variant === 'deep'
      ? 'bg-meridian-surfaceDeep'
      : 'bg-transparent';

  return (
    <div
      className={`${bgClass} border border-meridian-line rounded-none ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

// 2. InstrumentPanel (Dark Spotlight Container: Graphite #171A19, ivory text)
interface InstrumentPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const InstrumentPanel: React.FC<InstrumentPanelProps> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <div
      className={`bg-meridian-instrument text-meridian-ivory border border-meridian-ink rounded-none ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

// 3. SectionHeader (Editorial Asymmetric Style with Rail Label)
interface SectionHeaderProps {
  railLabel?: string; // e.g. "01 / LIVE RADAR"
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  railLabel,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div className={`editorial-rule pt-4 mb-6 ${className}`}>
      <div className="flex flex-col md:flex-row md:items-baseline justify-between gap-2">
        <div className="flex flex-col md:flex-row md:items-baseline gap-3 md:gap-6">
          {railLabel && (
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted shrink-0">
              {railLabel}
            </span>
          )}
          <div>
            <h2 className="text-xl md:text-2xl font-heading font-medium text-meridian-ink tracking-tight">
              {title}
            </h2>
            {description && (
              <p className="text-xs text-meridian-muted mt-0.5">{description}</p>
            )}
          </div>
        </div>
        {action && <div className="mt-2 md:mt-0">{action}</div>}
      </div>
    </div>
  );
};

// 4. StatusChip (Strict Accessibility Contrast on Light)
interface StatusChipProps {
  status: 'SCHEDULED' | 'ACTIVE' | 'CLOSED' | 'FORCE_CLOSED' | string;
  className?: string;
  size?: 'sm' | 'md' | 'compact';
}

export const StatusChip: React.FC<StatusChipProps> = ({
  status,
  className = '',
  size = 'compact',
}) => {
  const norm = status.toUpperCase();
  const sizeClasses =
    size === 'compact'
      ? 'h-[22px] px-2 text-[11px]'
      : size === 'sm'
      ? 'h-[20px] px-1.5 text-[10px]'
      : 'h-[26px] px-2.5 text-xs';

  let config = {
    bg: 'bg-meridian-surfaceDeep',
    text: 'text-meridian-ink',
    border: 'border-meridian-line',
    label: norm,
  };

  switch (norm) {
    case 'ACTIVE':
      config = {
        bg: 'bg-meridian-lime',
        text: 'text-meridian-ink font-bold',
        border: 'border-meridian-ink',
        label: 'ACTIVE',
      };
      break;
    case 'SCHEDULED':
      config = {
        bg: 'bg-meridian-surfaceDeep',
        text: 'text-meridian-muted',
        border: 'border-meridian-line',
        label: 'SCHEDULED',
      };
      break;
    case 'CLOSED':
      config = {
        bg: 'bg-transparent',
        text: 'text-meridian-ink font-medium',
        border: 'border-meridian-ink',
        label: 'CLOSED',
      };
      break;
    case 'FORCE_CLOSED':
      config = {
        bg: 'bg-meridian-orange',
        text: 'text-meridian-ink font-bold',
        border: 'border-meridian-ink',
        label: 'FORCE CLOSED',
      };
      break;
  }

  return (
    <span
      className={`inline-flex items-center justify-center font-mono tracking-wider uppercase border rounded-none shrink-0 ${config.bg} ${config.text} ${config.border} ${sizeClasses} ${className}`}
    >
      {norm === 'ACTIVE' && (
        <span className="w-1.5 h-1.5 rounded-full bg-meridian-ink mr-1.5 beacon-pulse" />
      )}
      <span>{config.label}</span>
    </span>
  );
};

// 5. MonoValue (Tabular Numerals Hero & Data Display)
interface MonoValueProps {
  label: string;
  value: string | number;
  subValue?: string;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  trend?: 'up' | 'down' | 'neutral';
  highlight?: 'lime' | 'orange' | 'default';
  className?: string;
}

export const MonoValue: React.FC<MonoValueProps> = ({
  label,
  value,
  subValue,
  size = 'md',
  highlight = 'default',
  className = '',
}) => {
  const sizeClass =
    size === 'hero'
      ? 'text-4xl md:text-5xl lg:text-6xl font-medium tracking-tight'
      : size === 'lg'
      ? 'text-2xl md:text-3xl font-medium tracking-tight'
      : size === 'md'
      ? 'text-lg md:text-xl font-medium'
      : 'text-sm font-medium';

  const highlightClass =
    highlight === 'lime'
      ? 'bg-meridian-lime text-meridian-ink px-1.5 py-0.5'
      : highlight === 'orange'
      ? 'text-meridian-orange font-bold'
      : 'text-meridian-ink';

  return (
    <div className={`flex flex-col ${className}`}>
      <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted mb-1">
        {label}
      </span>
      <div className="flex items-baseline gap-2">
        <span className={`font-mono tabular-nums ${sizeClass} ${highlightClass}`}>
          {value}
        </span>
        {subValue && (
          <span className="font-mono text-xs text-meridian-muted">
            {subValue}
          </span>
        )}
      </div>
    </div>
  );
};

// 6. RankBadge (Square Sharp Marker: L1 lime, L2/L3 deep ivory, Ln hairline)
interface RankBadgeProps {
  rank: number;
  isL1?: boolean;
  className?: string;
}

export const RankBadge: React.FC<RankBadgeProps> = ({
  rank,
  isL1 = rank === 1,
  className = '',
}) => {
  if (isL1) {
    return (
      <span
        className={`inline-flex items-center justify-center font-mono font-bold text-xs px-2 py-0.5 bg-meridian-lime text-meridian-ink border border-meridian-ink rounded-none ${className}`}
      >
        L1
      </span>
    );
  }

  if (rank <= 3) {
    return (
      <span
        className={`inline-flex items-center justify-center font-mono font-medium text-xs px-2 py-0.5 bg-meridian-surfaceDeep text-meridian-ink border border-meridian-line rounded-none ${className}`}
      >
        L{rank}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center justify-center font-mono text-xs px-2 py-0.5 text-meridian-muted border border-meridian-line rounded-none ${className}`}
    >
      L{rank}
    </span>
  );
};

// 7. TimelineMarker (Square Marker for Events: lime=bid, orange=ext, ink=system)
interface TimelineMarkerProps {
  type: 'BID' | 'EXTENSION' | 'STATUS' | 'CAPPED';
  className?: string;
}

export const TimelineMarker: React.FC<TimelineMarkerProps> = ({
  type,
  className = '',
}) => {
  let color = 'bg-meridian-ink';
  if (type === 'BID') color = 'bg-meridian-lime border border-meridian-ink';
  else if (type === 'EXTENSION' || type === 'CAPPED') color = 'bg-meridian-orange border border-meridian-ink';

  return (
    <span
      className={`w-2.5 h-2.5 shrink-0 rounded-none inline-block ${color} ${className}`}
    />
  );
};

// 8. HairlineTable (Light Table Wrapper with Sticky Header and Subtle Row Hover)
interface HairlineTableProps {
  children: React.ReactNode;
  className?: string;
}

export const HairlineTable: React.FC<HairlineTableProps> = ({
  children,
  className = '',
}) => {
  return (
    <div className={`overflow-x-auto border border-meridian-line bg-meridian-surface ${className}`}>
      <table className="w-full text-left border-collapse text-meridian-ink">
        {children}
      </table>
    </div>
  );
};

