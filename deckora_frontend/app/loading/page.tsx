'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Loading from '@/components/ui/Loading';
import Icon from '@/components/ui/Icon';
import { generatePresentation } from '@/lib/api';

export default function LoadingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const generationId = searchParams.get('id');

  useEffect(() => {
    if (!generationId) {
      // If no ID, just show loading (for direct access to /loading)
      return;
    }

    // Check if we already have a result (in case of page refresh)
    const existingResult = sessionStorage.getItem(`generation_result_${generationId}`);
    if (existingResult) {
      try {
        const response = JSON.parse(existingResult);
        handleGenerationResult(response, generationId, router, setError);
        return;
      } catch (e) {
        console.error('Error parsing existing result:', e);
      }
    }

    // Get form data from sessionStorage
    const formDataStr = sessionStorage.getItem(`generation_request_${generationId}`);
    if (!formDataStr) {
      setError('Form data not found. Please try again.');
      return;
    }

    let formData;
    try {
      formData = JSON.parse(formDataStr);
    } catch (e) {
      setError('Invalid form data. Please try again.');
      return;
    }

    // Make the API call
    const generatePresentationAsync = async () => {
      try {
        const response = await generatePresentation(formData);
        
        // Store the response in sessionStorage
        sessionStorage.setItem(`generation_result_${generationId}`, JSON.stringify(response));
        
        // Handle the result
        handleGenerationResult(response, generationId, router, setError);
      } catch (error) {
        console.error('Error generating presentation:', error);
        const errorMsg = error instanceof Error ? error.message : 'An unexpected error occurred';
        setError(errorMsg);
        
        // Store error in sessionStorage
        sessionStorage.setItem(`generation_result_${generationId}`, JSON.stringify({
          status: 'error',
          error: errorMsg
        }));
      }
    };

    generatePresentationAsync();
  }, [generationId, router]);

  if (error) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gradient-to-b from-white to-primary-50">
        <div className="flex flex-col items-center justify-center text-center px-4">
          <div className="mb-4 rounded-full bg-red-100 p-4">
            <Icon name="error" size={48} className="text-red-500" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Generation Failed</h2>
          <p className="text-base text-slate-600 mb-4">{error}</p>
          <button
            onClick={() => router.push('/')}
            className="rounded-lg bg-primary-500 px-6 py-2 text-white hover:bg-primary-600 transition-colors"
          >
            Start Over
          </button>
        </div>
      </div>
    );
  }

  return <Loading />;
}

// Helper function to handle generation result
function handleGenerationResult(
  response: any,
  generationId: string,
  router: any,
  setError: (error: string | null) => void
) {
  if (response.status === 'success') {
    const webSlidesResult = response.outputs?.web_slides_result;
    
    if (webSlidesResult?.slides_data) {
      // Store slides data in sessionStorage for immediate access
      const presentationId = generationId;
      sessionStorage.setItem(`presentation_${presentationId}`, JSON.stringify(webSlidesResult.slides_data));
      
      // Redirect to presentation page
      router.push(`/presentation/${presentationId}`);
    } else {
      // Fallback: If we have Google Slides URL, open it
      const slidesResult = response.outputs?.slideshow_export_result || response.outputs?.slides_export_result;
      if (slidesResult?.shareable_url) {
        window.open(slidesResult.shareable_url, '_blank');
        // Redirect back to home after opening Google Slides
        setTimeout(() => {
          router.push('/');
        }, 1000);
      } else {
        setError('Presentation generated but no slides data available.');
      }
    }
  } else if (response.status === 'error') {
    setError(response.error || 'An error occurred');
  }
}

