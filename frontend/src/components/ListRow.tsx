import type { ReactNode } from 'react';

interface ListRowProps {
  icon?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  onClick?: () => void;
}

export function ListRow({ icon, title, subtitle, trailing, onClick }: ListRowProps) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center gap-3.5 bg-white border border-border rounded-2xl px-4 py-3.5 ${
        onClick ? 'cursor-pointer' : ''
      }`}
    >
      {icon && (
        <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-xl shrink-0">
          {icon}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-[14.5px] text-ink">{title}</div>
        {subtitle && <div className="mt-0.5 text-xs text-sub">{subtitle}</div>}
      </div>
      {trailing}
    </div>
  );
}

export function Chevron() {
  return <div className="text-[#C6D2CE] text-lg shrink-0">›</div>;
}

export function StatusTag({ label, tone = 'teal' }: { label: string; tone?: 'teal' | 'warn' }) {
  const classes = tone === 'teal' ? 'text-teal bg-teal-soft' : 'text-warn bg-warn-bg';
  return <span className={`font-heading font-bold text-[11px] px-2.5 py-1 rounded-full shrink-0 ${classes}`}>{label}</span>;
}
