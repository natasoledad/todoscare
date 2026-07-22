export function Dots({ count, active }: { count: number; active: number }) {
  return (
    <div className="flex gap-1.5 justify-center">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`h-1.5 rounded-full transition-all duration-200 ${
            i === active ? 'w-5 bg-teal' : 'w-1.5 bg-[#DCE6E3]'
          }`}
        />
      ))}
    </div>
  );
}
