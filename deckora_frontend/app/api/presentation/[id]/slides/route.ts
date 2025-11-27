import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join, resolve } from 'path';
import type { SlidesData } from '@/types/slides';

/**
 * API route to fetch slides data for a presentation
 * GET /api/presentation/[id]/slides
 * 
 * Falls back to reading from presentation_agent/output/6_slides_data.json if backend API is unavailable
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const presentationId = params.id;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
    
    // Try to fetch from backend API first
    try {
      const response = await fetch(`${apiUrl}/presentation/${presentationId}/slides`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const slidesData: SlidesData = await response.json();
        console.log('✅ Loaded slides data from backend API');
        return NextResponse.json(slidesData);
      }
    } catch (apiError) {
      console.warn('Backend API unavailable, falling back to local file:', apiError);
    }

    // Fallback: Read from local file system
    // When backend API is unavailable, load the default 6_slides_data.json file
    // This allows quick preview of the presentation without running the backend
    // Path: from deckora_frontend to ../presentation_agent/output/6_slides_data.json
    try {
      // Use resolve() for more reliable path resolution
      // In Next.js, process.cwd() is the project root (deckora_frontend)
      // We need to go up one level to reach presentation_agent
      const filePath = resolve(process.cwd(), '..', 'presentation_agent', 'output', '6_slides_data.json');
      console.log('Attempting to read file from:', filePath);
      const fileContents = await readFile(filePath, 'utf-8');
      const slidesData: SlidesData = JSON.parse(fileContents);
      console.log(`✅ Loaded slides data from local file (presentationId: ${presentationId})`);
      return NextResponse.json(slidesData);
    } catch (fileError) {
      console.error('Failed to read local 6_slides_data.json:', fileError);
      // If file doesn't exist, provide a helpful error message
      const err = fileError as NodeJS.ErrnoException;
      if (err.code === 'ENOENT') {
        return NextResponse.json(
          { 
            error: 'Slides data file not found. Please run the pipeline to generate 6_slides_data.json',
            hint: 'The file should be at: presentation_agent/output/6_slides_data.json',
            attemptedPath: resolve(process.cwd(), '..', 'presentation_agent', 'output', '6_slides_data.json'),
            cwd: process.cwd()
          },
          { status: 404 }
        );
      }
      return NextResponse.json(
        { 
          error: 'Failed to fetch slides data from backend API or local file',
          details: err.message || String(err)
        },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('Error fetching slides data:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

