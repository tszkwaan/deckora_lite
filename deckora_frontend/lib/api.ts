export interface GeneratePresentationRequest {
  report_url?: string;
  report_content?: string;
  scenario?: string;
  duration: string;
  target_audience?: string;
  custom_instruction?: string;
  style_images?: string[];
}

export interface GeneratePresentationResponse {
  status: 'success' | 'error';
  outputs?: {
    web_slides_result?: {
      slides_data?: any;
    };
    slideshow_export_result?: {
      shareable_url?: string;
      presentation_id?: string;
    };
    slides_export_result?: {
      shareable_url?: string;
      presentation_id?: string;
    };
  };
  google_slides_url?: string;
  error?: string;
}

export async function generatePresentation(
  data: GeneratePresentationRequest
): Promise<GeneratePresentationResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
  
  try {
    const response = await fetch(`${apiUrl}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        status: 'error',
        error: errorData.error || `API returned status ${response.status}`,
      };
    }

    const result: GeneratePresentationResponse = await response.json();
    return result;
  } catch (error) {
    return {
      status: 'error',
      error: error instanceof Error ? error.message : 'Failed to generate presentation',
    };
  }
}

