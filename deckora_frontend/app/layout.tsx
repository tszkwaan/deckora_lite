import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Deckora - Transform Reports into Presentations',
  description: 'Upload your document. Let our multi-agent system craft your slides and presenter script.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="light">
      <body className={`${inter.variable} font-display bg-white text-slate-800`}>
        {children}
      </body>
    </html>
  );
}
