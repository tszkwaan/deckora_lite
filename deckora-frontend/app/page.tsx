import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import Hero from '@/components/layout/Hero';
import Features from '@/components/layout/Features';
import PresentationForm from '@/components/forms/PresentationForm';

export default function Home() {
  return (
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden">
      <Header />
      <main className="flex-grow">
        <Hero />
        <section className="relative -mt-24 pb-16 sm:-mt-20 sm:pb-24 md:-mt-16 md:pb-24">
          <div className="relative z-20 mx-auto max-w-[640px] px-4">
            <PresentationForm />
          </div>
        </section>
        <Features />
      </main>
      <Footer />
    </div>
  );
}
