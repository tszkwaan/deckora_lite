export interface PresentationFormData {
  reportUrl: string;
  duration: string;
  scenario: string;
  targetAudience: string;
  customInstruction: string;
}

export type Scenario = 'academic' | 'sales' | 'internal_update' | 'conference_talk';

export type TargetAudience = 'students' | 'customers' | 'executives' | 'general_public';

export interface FormErrors {
  reportUrl?: string;
  duration?: string;
}

