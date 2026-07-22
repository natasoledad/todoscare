import type { ReactNode } from 'react';

export function BottomSheet({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="absolute inset-0 z-20 flex items-end bg-[#0F2A24]/45" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-h-[75%] flex flex-col gap-3 rounded-t-[22px] bg-white px-[22px] pt-[22px] pb-[30px] animate-fade-up overflow-y-auto"
      >
        {children}
      </div>
    </div>
  );
}
