import type { ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
}

const baseStyles =
  'inline-flex items-center justify-center rounded px-5 py-2 text-sm font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50';

const variantStyles: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-nflix-red text-white hover:bg-nflix-red-dark',
  secondary: 'bg-white/15 text-white hover:bg-white/25',
};

export const Button = ({ variant = 'primary', className = '', ...rest }: ButtonProps) => {
  return <button className={`${baseStyles} ${variantStyles[variant]} ${className}`} {...rest} />;
};
