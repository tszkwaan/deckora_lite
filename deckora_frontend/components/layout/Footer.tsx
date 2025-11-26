import React from 'react';

const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="w-full bg-white py-8">
      <div className="mx-auto flex max-w-7xl items-center justify-center px-4">
        <p className="text-sm text-slate-500">© {currentYear} Deckora. All rights reserved.</p>
      </div>
    </footer>
  );
};

export default Footer;

