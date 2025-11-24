'use client';

import { useState } from 'react';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import Hero from '@/components/layout/Hero';
import Features from '@/components/layout/Features';
import PresentationForm from '@/components/forms/PresentationForm';
import Loading from '@/components/ui/Loading';

export default function Home() {
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <>
      {/* Full-screen loading overlay */}
      {isSubmitting && (
        <div className="fixed inset-0 z-[9999] bg-gradient-to-b from-white to-primary-50">
          <Loading />
        </div>
      )}
      
      {/* Page content - hidden when loading */}
      <div className={`relative flex min-h-screen w-full flex-col overflow-x-hidden ${isSubmitting ? 'opacity-0 pointer-events-none' : ''}`}>
        <Header />
        <main className="flex-grow">
          <Hero />
          <section className="relative -mt-24 pb-16 sm:-mt-20 sm:pb-24 md:-mt-16 md:pb-24">
            <div className="relative z-20 mx-auto max-w-[640px] px-4">
              <PresentationForm onSubmittingChange={setIsSubmitting} />
            </div>
          </section>
          <Features />
        </main>
        <Footer />
      </div>
    </>
  );
}
