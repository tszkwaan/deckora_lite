import React from 'react';
import Icon from '../ui/Icon';

interface Feature {
  icon: string;
  title: string;
  description: string;
}

const Features: React.FC = () => {
  const features: Feature[] = [
    {
      icon: 'auto_awesome',
      title: 'Multi-Agent Reasoning',
      description: 'Different smart tools work together to create the best presentation.',
    },
    {
      icon: 'description',
      title: 'Smart Understanding',
      description: 'The system intelligently pulls out the most important points from your documents.',
    },
    {
      icon: 'slideshow',
      title: 'Export-Ready Slides',
      description: 'Get presentations ready for popular platforms like Google Slides or PowerPoint instantly.',
    },
  ];

  return (
    <section className="w-full bg-primary-50 py-16 sm:py-20 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 px-4 md:grid-cols-3 md:gap-10">
        {features.map((feature, index) => (
          <div key={index} className="flex flex-col items-center gap-4 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-white text-primary-500 shadow-md">
              <Icon name={feature.icon} size={32} />
            </div>
            <h3 className="text-xl font-bold text-slate-900">{feature.title}</h3>
            <p className="text-base text-slate-600">{feature.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Features;

