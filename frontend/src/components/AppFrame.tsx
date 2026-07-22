import type { ReactNode } from 'react';

/**
 * Mobile-first content column, pinned to the viewport height. Full-bleed on
 * a phone; on wider viewports it centers as a constrained column — no fake
 * device bezel, the real device chrome (status bar, home indicator) is
 * supplied by the OS/PWA shell. Screens fill this frame and manage their
 * own internal scrolling.
 */
export function AppFrame({ children }: { children: ReactNode }) {
  return (
    <div className="h-dvh w-full flex justify-center bg-bg overflow-hidden">
      <div className="relative w-full max-w-[430px] h-full bg-bg sm:shadow-[0_0_0_1px_rgba(15,42,36,0.06)] overflow-hidden">
        {children}
      </div>
    </div>
  );
}
