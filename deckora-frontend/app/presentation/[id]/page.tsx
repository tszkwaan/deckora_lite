'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import type { SlidesData, SlideData } from '@/types/slides';
import Loading from '@/components/ui/Loading';

// Dynamic import for Mermaid (client-side only)
let mermaid: any = null;
const loadMermaid = async () => {
  if (typeof window !== 'undefined' && !mermaid) {
    try {
      const mermaidModule = await import('mermaid');
      mermaid = mermaidModule.default;
      mermaid.initialize({ 
        startOnLoad: false,
        theme: 'default',
        themeVariables: {
          primaryColor: '#7C3AED',
          primaryTextColor: '#1F2937',
          primaryBorderColor: '#7C3AED',
          lineColor: '#7C3AED',
          secondaryColor: '#EC4899',
          tertiaryColor: '#10B981'
        }
      });
    } catch (error) {
      console.error('Failed to load Mermaid:', error);
    }
  }
  return mermaid;
};

// Helper function to render Mermaid diagrams in any container
const renderMermaidInContainer = async (container: HTMLElement) => {
  const mermaidLib = await loadMermaid();
  if (mermaidLib && container) {
    const mermaidElements = container.querySelectorAll('pre.mermaid, .mermaid');
    if (mermaidElements.length > 0) {
      mermaidElements.forEach((element, index) => {
        const id = `mermaid-${Date.now()}-${index}`;
        if (!element.id) {
          element.id = id;
        }
        try {
          // Mermaid v10+ API
          if (mermaidLib.run) {
            mermaidLib.run({
              nodes: [element],
              suppressErrors: true
            });
          } else {
            // Fallback for older API
            mermaidLib.init(undefined, element);
          }
        } catch (error) {
          console.error('Mermaid rendering error:', error);
        }
      });
    }
  }
};

// Component to render slide HTML and fix layout for charts if needed
function SlideContent({ 
  html, 
  chartsNeeded 
}: { 
  html: string; 
  chartsNeeded?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Set the HTML content
    containerRef.current.innerHTML = html;
    
    // Render Mermaid diagrams
    setTimeout(() => renderMermaidInContainer(containerRef.current!), 100);

    // If chart is needed but layout is wrong, fix it: title on top, content and chart side by side
    if (chartsNeeded) {
      const slideContent = containerRef.current.querySelector('.slide-content');
      if (slideContent) {
        const slideTitle = slideContent.querySelector('.slide-title');
        const slideBody = slideContent.querySelector('.slide-body');
        const chartContainer = slideContent.querySelector('.chart-container');
        
        // Check if layout needs fixing (title should be on top, body and chart side by side)
        if (slideTitle && slideBody && chartContainer) {
          // Check if body and chart are direct children (wrong layout)
          const bodyIndex = Array.from(slideContent.children).indexOf(slideBody);
          const chartIndex = Array.from(slideContent.children).indexOf(chartContainer);
          const titleIndex = Array.from(slideContent.children).indexOf(slideTitle);
          
          // If title is not first, or body/chart are not in a wrapper, restructure
          if (titleIndex !== 0 || (bodyIndex > 0 && chartIndex > 0 && Math.abs(bodyIndex - chartIndex) > 1)) {
            // Create wrapper for body and chart
            const contentWrapper = document.createElement('div');
            contentWrapper.className = 'slide-content-wrapper';
            contentWrapper.style.display = 'grid';
            contentWrapper.style.gridTemplateColumns = '1fr 1fr';
            contentWrapper.style.gap = '40px';
            contentWrapper.style.alignItems = 'center';
            
            // Move body and chart into wrapper
            const bodyClone = slideBody.cloneNode(true) as HTMLElement;
            const chartClone = chartContainer.cloneNode(true) as HTMLElement;
            contentWrapper.appendChild(bodyClone);
            contentWrapper.appendChild(chartClone);
            
            // Remove originals
            slideBody.remove();
            chartContainer.remove();
            
            // Insert wrapper after title
            if (slideTitle.nextSibling) {
              slideTitle.parentElement?.insertBefore(contentWrapper, slideTitle.nextSibling);
            } else {
              slideTitle.parentElement?.appendChild(contentWrapper);
            }
            
            // Update layout class
            slideContent.classList.remove('slide-text-only');
            slideContent.classList.add('slide-with-chart');
          }
        }
      }
    }
  }, [html, chartsNeeded]);

  return <div ref={containerRef} className="w-full h-full overflow-hidden" />;
}

// Component for thumbnail previews (scaled down)
function ThumbnailSlideContent({ html }: { html: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Set the HTML content
    containerRef.current.innerHTML = html;
    
    // Render Mermaid diagrams in thumbnail (with smaller scale)
    setTimeout(() => {
      if (containerRef.current) {
        renderMermaidInContainer(containerRef.current);
      }
    }, 150);
  }, [html]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0"
      style={{
        transform: 'scale(0.15)',
        transformOrigin: 'top left',
        width: '666.67%', // 100 / 0.15
        height: '666.67%',
        pointerEvents: 'none',
      }}
    />
  );
}

export default function PresentationViewPage() {
  const params = useParams();
  const router = useRouter();
  const presentationId = params.id as string;
  
  const [slidesData, setSlidesData] = useState<SlidesData | null>(null);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch slides data
    const fetchSlidesData = async () => {
      try {
        setIsLoading(true);
        
        // Option 1: Try to get from sessionStorage (if just generated from pipeline)
        // This is the primary method when coming from the landing page after pipeline completion
        const cachedData = sessionStorage.getItem(`presentation_${presentationId}`);
        if (cachedData) {
          try {
            const data: SlidesData = JSON.parse(cachedData);
            setSlidesData(data);
            setIsLoading(false);
            console.log('✅ Loaded slides data from sessionStorage');
            return;
          } catch (e) {
            console.warn('Failed to parse cached data:', e);
            // Invalid JSON, continue to API fetch
          }
        }
        
        // Option 2: Try Next.js API route first (it will fallback to local file)
        // This is the preferred method as it handles both backend API and local file fallback
        try {
          const apiRouteResponse = await fetch(`/api/presentation/${presentationId}/slides`);
          if (apiRouteResponse.ok) {
            const data: SlidesData = await apiRouteResponse.json();
            setSlidesData(data);
            setIsLoading(false);
            console.log('✅ Loaded slides data from Next.js API route');
            return;
          } else {
            const errorData = await apiRouteResponse.json().catch(() => ({}));
            throw new Error(errorData.error || `API returned status ${apiRouteResponse.status}`);
          }
        } catch (routeErr) {
          console.warn('Next.js API route fetch failed:', routeErr);
        }
        
        // Option 3: Try backend API endpoint directly (if Next.js route failed)
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
        try {
          const response = await fetch(`${apiUrl}/presentation/${presentationId}/slides`);
          if (response.ok) {
            const data: SlidesData = await response.json();
            setSlidesData(data);
            setIsLoading(false);
            console.log('✅ Loaded slides data from backend API');
            return;
          }
        } catch (apiErr) {
          console.warn('Backend API fetch failed:', apiErr);
        }
        
        // If all methods fail
        throw new Error('Failed to load slides data. Make sure the pipeline has generated slides_data.json or the backend API is running.');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load presentation');
        console.error('Error loading slides:', err);
      } finally {
        setIsLoading(false);
      }
    };

    if (presentationId) {
      fetchSlidesData();
    }
  }, [presentationId]);

  const handlePreviousSlide = () => {
    if (slidesData && currentSlideIndex > 0) {
      setCurrentSlideIndex(currentSlideIndex - 1);
    }
  };

  const handleNextSlide = () => {
    if (slidesData && currentSlideIndex < slidesData.slides.length - 1) {
      setCurrentSlideIndex(currentSlideIndex + 1);
    }
  };

  const handleSlideThumbnailClick = (index: number) => {
    setCurrentSlideIndex(index);
  };

  const formatTranscriptTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getCurrentTranscript = (): string => {
    if (!slidesData) return '';
    
    const currentSlide = slidesData.slides[currentSlideIndex];
    if (!currentSlide?.script) return '';

    const script = currentSlide.script;
    let transcript = '';
    let timeOffset = 0;

    if (script.opening_line) {
      transcript += `<p><span class="font-bold text-primary">${formatTranscriptTime(timeOffset)}</span> ${script.opening_line}</p>`;
      // Use calculated opening_line_time if available, otherwise calculate from word count
      const openingTime = (script as any).opening_line_time || Math.max(1, Math.round(script.opening_line.split(' ').length / 2));
      timeOffset += openingTime;
    }

    script.main_content.forEach((point) => {
      transcript += `<p><span class="font-bold text-primary">${formatTranscriptTime(timeOffset)}</span> ${point.explanation}</p>`;
      timeOffset += point.estimated_time || 10;
    });

    return transcript;
  };

  if (isLoading) {
    return <Loading />;
  }

  if (error || !slidesData) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-lg font-semibold text-red-600">Error loading presentation</div>
          <p className="text-slate-600">{error || 'No slides data available'}</p>
          <button
            onClick={() => router.push('/')}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-white hover:bg-primary-hover"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const currentSlide = slidesData.slides[currentSlideIndex];
  const transcript = getCurrentTranscript();

  return (
    <>
      {/* Inject global CSS */}
      <style dangerouslySetInnerHTML={{ __html: slidesData.global_css }} />
      <style>{`
        .slide-content {
          height: 100% !important;
          width: 100% !important;
          max-height: 100% !important;
          overflow: hidden !important;
          box-sizing: border-box !important;
        }
        .slide-content-wrapper {
          height: 100% !important;
          max-height: 100% !important;
        }
        .chart-container {
          height: 100% !important;
          width: 100% !important;
          max-height: 100% !important;
          padding: 0 !important;
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
        }
        .chart-image {
          max-width: 100% !important;
          max-height: 100% !important;
          width: auto !important;
          height: auto !important;
          object-fit: contain !important;
          display: block !important;
        }
      `}</style>
      
      <div className="flex h-screen w-full flex-col overflow-hidden">
        {/* Header */}
        <header className="sticky top-0 z-50 flex flex-shrink-0 items-center border-b border-solid border-slate-200/80 bg-white/60 py-3 backdrop-blur-md">
          <div className="flex w-full items-center">
            <div className="flex items-center pl-[50px]">
              <h2 className="text-slate-900 text-xl font-bold">Deckora</h2>
            </div>
            <div className="flex flex-1 items-center justify-center">
              <p className="text-sm text-slate-600">
                Presentation: {slidesData.metadata.title}
              </p>
            </div>
          </div>
        </header>

        <main className="flex flex-grow overflow-hidden">
          {/* Left Sidebar - Slide Thumbnails */}
          <aside className="hidden h-full w-64 flex-shrink-0 flex-col border-r border-slate-200 bg-white sm:flex">
            <div className="flex-grow overflow-y-auto p-4">
              <div className="flex flex-col gap-4">
                {slidesData.slides.map((slide, index) => (
                  <div
                    key={slide.slide_number}
                    onClick={() => handleSlideThumbnailClick(index)}
                    className={`relative cursor-pointer rounded-lg border-2 p-0.5 transition-all ${
                      index === currentSlideIndex
                        ? 'bg-gradient-to-br from-primary to-secondary border-transparent'
                        : 'border-transparent hover:border-primary/50'
                    }`}
                  >
                    {/* Thumbnail - render slide HTML in a small container */}
                    <div className="aspect-[16/9] w-full rounded-md bg-white overflow-hidden relative">
                      {/* Render slide HTML scaled down for thumbnail */}
                      <ThumbnailSlideContent html={slide.html} />
                    </div>
                    <span className="absolute left-2 top-2 rounded-full bg-black/50 px-2 py-0.5 text-xs font-medium text-white">
                      {slide.slide_number}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          {/* Main Content Area */}
          <div className="relative flex flex-1 flex-col overflow-hidden min-h-0">
            <div className="flex flex-1 items-center justify-center p-4 sm:p-8 min-h-0 overflow-hidden">
              {/* Slide container - responsive like Google Slides, maintains 16:9 aspect ratio, fits within red box */}
              <div className="aspect-video rounded-xl bg-white shadow-xl overflow-hidden" style={{ maxWidth: '1200px', maxHeight: '100%', width: '100%', height: 'auto' }}>
                {/* Render current slide HTML */}
                <div className="w-full h-full overflow-hidden">
                  <SlideContent 
                    html={currentSlide.html} 
                    chartsNeeded={currentSlide.charts_needed}
                  />
                </div>
              </div>
            </div>

            {/* Bottom Bar - Transcript and Navigation */}
            <div className="flex-shrink-0 flex items-end justify-between gap-6 border-t border-slate-200 bg-white/60 p-4 backdrop-blur-md">
              <div className="flex-grow">
                <div className="w-full max-w-4xl mx-auto">
                  <h3 className="text-sm font-semibold text-slate-800 mb-2">Transcript</h3>
                  <div
                    className="prose prose-slate text-sm text-slate-600 pr-4 h-[228px] overflow-y-auto"
                    dangerouslySetInnerHTML={{ __html: transcript || '<p class="text-slate-400 italic">No transcript available for this slide.</p>' }}
                  />
                </div>
              </div>
              <div className="flex flex-shrink-0 items-center justify-center gap-6">
                <button
                  onClick={handlePreviousSlide}
                  disabled={currentSlideIndex === 0}
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-slate-500 shadow-md transition-colors hover:bg-primary-lighter hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="material-symbols-outlined text-3xl">arrow_back</span>
                </button>
                <p className="text-sm font-medium text-slate-600">
                  {currentSlideIndex + 1} / {slidesData.slides.length}
                </p>
                <button
                  onClick={handleNextSlide}
                  disabled={currentSlideIndex === slidesData.slides.length - 1}
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-slate-500 shadow-md transition-colors hover:bg-primary-lighter hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="material-symbols-outlined text-3xl">arrow_forward</span>
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  );
}

