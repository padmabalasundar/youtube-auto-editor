import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="min-h-screen bg-nflix-black text-white">
      <header className="sticky top-0 z-10 bg-gradient-to-b from-black/80 to-transparent px-4 py-4 sm:px-8">
        <Link to="/" className="text-2xl font-black tracking-tight text-nflix-red">
          CLIPFLIX
        </Link>
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-8">{children}</main>
    </div>
  );
};
