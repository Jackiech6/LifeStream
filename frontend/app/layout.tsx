import type { Metadata } from 'next';
import './globals.css';
import Navigation from '@/components/Navigation';

export const metadata: Metadata = {
  title: 'LifeStream - Intelligent Diary',
  description: 'Automated multi-modal pipeline that converts raw video footage into structured, searchable daily journals',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <Navigation />
        <main className="min-h-screen bg-gray-50">{children}</main>
      </body>
    </html>
  );
}
