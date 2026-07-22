export function ScreenHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="px-[22px] pt-5 pb-1.5">
      <div className="font-heading font-extrabold text-[22px] leading-tight text-ink">{title}</div>
      {subtitle && <div className="mt-1 text-[13px] leading-snug text-sub">{subtitle}</div>}
    </div>
  );
}
