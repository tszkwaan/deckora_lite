/**
 * Types for slides data from backend
 */

export interface SlideData {
  slide_number: number;
  html: string;
  css: string;
  design_spec: {
    title_font_size?: number;
    subtitle_font_size?: number;
    body_font_size?: number;
    title_position?: {
      x_percent: number;
      y_percent: number;
      width_percent: number;
    };
    subtitle_position?: {
      x_percent: number;
      y_percent: number;
      width_percent: number;
    };
    spacing?: {
      title_to_subtitle?: number;
      subtitle_to_content?: number;
      line_spacing?: number;
    };
    alignment?: {
      title?: 'left' | 'center' | 'right';
      subtitle?: 'left' | 'center' | 'right';
      body?: 'left' | 'center' | 'right';
    };
  };
  speaker_notes: string;
  script: {
    slide_number: number;
    slide_title: string;
    opening_line?: string;
    main_content: Array<{
      point: string;
      explanation: string;
      estimated_time: number;
    }>;
    transitions?: {
      from_previous?: string;
      to_next?: string;
    };
    key_phrases?: string[];
    notes?: string;
  } | null;
  title: string;
  has_icons: boolean;
  charts_needed?: boolean;
  chart_spec?: {
    chart_type: 'bar' | 'line' | 'pie';
    data: Record<string, number | number[] | null>;
    title: string;
    x_label?: string;
    y_label?: string;
    width?: number;
    height?: number;
    color?: string;
    colors?: string[];
  } | null;
}

export interface SlidesDataMetadata {
  title: string;
  total_slides: number;
  scenario: string;
  duration: string;
  target_audience: string;
  theme_colors: {
    primary: string;
    secondary: string;
    background: string;
    text: string;
  };
}

export interface SlidesData {
  metadata: SlidesDataMetadata;
  global_css: string;
  slides: SlideData[];
}

