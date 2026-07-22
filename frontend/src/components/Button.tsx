import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'ghost' | 'outline';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: Variant;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-teal text-white active:scale-[0.97]',
  ghost: 'bg-teal-soft text-teal-dark active:scale-[0.97]',
  outline: 'bg-white text-ink border-[1.5px] border-border-strong active:scale-[0.97]',
};

export function Button({ children, variant = 'primary', className = '', disabled, ...rest }: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={`rounded-[14px] px-[18px] py-[14px] font-heading font-bold text-[15px] leading-none transition-transform duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-45 ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
