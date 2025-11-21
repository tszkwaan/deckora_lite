import React from 'react';

const Hero: React.FC = () => {
  return (
    <section className="relative w-full overflow-hidden bg-gradient-to-b from-white to-primary-50">
      <div className="absolute inset-0 z-0">
        <div className="absolute bottom-0 left-[-20%] top-0 w-[40%] bg-gradient-to-r from-white via-white/50 to-transparent" />
        <div className="absolute bottom-0 right-[-20%] top-0 w-[40%] bg-gradient-to-l from-white via-white/50 to-transparent" />
      </div>
      <div className="relative z-10 mx-auto flex max-w-7xl flex-col items-center px-4 py-20 text-center sm:py-24 md:py-32">
        <div className="flex max-w-3xl flex-col gap-4">
          <h1 className="text-4xl font-black tracking-tighter text-slate-900 sm:text-5xl md:text-6xl">
            Transform Any Report Into a{' '}
            <span className="primary-gradient-text">
              Polished Presentation
            </span>
          </h1>
          <h2 className="text-base font-normal text-slate-600 sm:text-lg md:text-xl">
            Upload your document. Let our multi-agent system craft your slides and presenter script.
          </h2>
        </div>
      </div>
    </section>
  );
};

export default Hero;

