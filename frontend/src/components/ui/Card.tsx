import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
}

export const Card = ({ children, className = '' }: CardProps) => {
  return (
    <div
      className={`rounded-md bg-nflix-surface p-4 transition-transform duration-200 hover:scale-[1.03] hover:shadow-xl hover:shadow-black/50 ${className}`}
    >
      {children}
    </div>
  );
};
