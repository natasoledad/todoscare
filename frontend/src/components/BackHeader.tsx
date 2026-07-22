import type { ReactNode } from 'react';

export function BackHeader({ title, onBack, right }: { title: ReactNode; onBack: () => void; right?: ReactNode }) {
  return (
    <div className="flex items-center gap-3 px-[22px] pt-[18px]">
      <div onClick={onBack} className="cursor-pointer text-lg text-sub select-none">
        ←
      </div>
      <div className="flex-1 font-heading font-extrabold text-[17px] text-ink">{title}</div>
      {right}
    </div>
  );
}
