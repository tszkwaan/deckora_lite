'use client';

import React from 'react';
import Icon from './Icon';

interface LoadingProps {
  message?: string;
  subMessage?: string;
}

const Loading: React.FC<LoadingProps> = ({ 
  message = 'Your presentation is on the way.',
  subMessage = 'This step takes about a minute—thank you for waiting.'
}) => {
  const circles = [
    { icon: 'auto_awesome', color: 'primary', delay: 0 },
    { icon: 'description', color: 'secondary', delay: 0.4 },
    { icon: 'hourglass_empty', color: 'primary', delay: 0.8 },
    { icon: 'slideshow', color: 'primary', delay: 1.2 },
    { icon: 'rocket_launch', color: 'secondary', delay: 1.6 },
  ];

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gradient-to-b from-white to-primary-50">
        <div className="flex flex-col items-center justify-center">
          {/* Icon circles row */}
          <div className="mb-12 flex items-center justify-center gap-6 sm:gap-8">
            {circles.map((circle, index) => (
              <div
                key={index}
                className={`
                  relative rounded-full bg-white flex items-center justify-center shadow-lg
                  border-2
                  ${circle.color === 'primary' ? 'border-primary-100' : 'border-secondary-500/20'}
                  ${index === 2 ? 'h-24 w-24 sm:h-28 sm:w-28 border-4 border-primary-500' : 'h-20 w-20 sm:h-24 sm:w-24'}
                `}
                style={{
                  animation: `circle-pulse 2s ease-in-out infinite`,
                  animationDelay: `${circle.delay}s`,
                }}
              >
                <Icon 
                  name={circle.icon} 
                  size={index === 2 ? 48 : 40} 
                  className={circle.color === 'primary' ? 'text-primary-500' : 'text-secondary-500'} 
                />
              </div>
            ))}
          </div>

          {/* Loading text */}
          <div className="text-center px-4">
            <p className="text-xl sm:text-2xl font-bold text-slate-900 mb-2">{message}</p>
            <p className="text-base sm:text-lg text-slate-600">{subMessage}</p>
          </div>
        </div>
      </div>
  );
};

export default Loading;

