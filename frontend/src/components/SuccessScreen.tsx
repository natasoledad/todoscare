import type { ReactNode } from 'react';

export function SuccessScreen({
  emoji,
  title,
  description,
  badge,
  children,
}: {
  emoji: string;
  title: string;
  description: string;
  badge?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-4 px-8 text-center animate-fade-up overflow-y-auto scrollhide">
      <div className="w-[84px] h-[84px] rounded-full bg-teal-soft flex items-center justify-center text-4xl animate-pop-in shrink-0">
        {emoji}
      </div>
      <div className="font-heading font-extrabold text-[21px] leading-tight text-ink">{title}</div>
      <div className="text-sm leading-relaxed text-sub max-w-[240px]">{description}</div>
      {badge}
      {children}
    </div>
  );
}

export function LevelBadge({ emoji, label }: { emoji: string; label: string }) {
  return (
    <div className="flex items-center gap-2 bg-warn-bg border border-warn-border rounded-xl px-4 py-2.5">
      <span className="text-lg">{emoji}</span>
      <span className="font-heading font-bold text-[13px] text-[#8A6A00]">{label}</span>
    </div>
  );
}
