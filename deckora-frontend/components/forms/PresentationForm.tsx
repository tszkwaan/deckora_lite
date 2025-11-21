'use client';

import React, { useState, FormEvent } from 'react';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import Button from '../ui/Button';
import Icon from '../ui/Icon';
import { PresentationFormData, FormErrors } from '@/types';
import { SCENARIOS, TARGET_AUDIENCES, DEFAULT_DURATION } from '@/lib/constants';

const PresentationForm: React.FC = () => {
  const [showConfig, setShowConfig] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState<PresentationFormData>({
    reportUrl: '',
    duration: DEFAULT_DURATION,
    scenario: '',
    targetAudience: '',
    customInstruction: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.reportUrl.trim()) {
      newErrors.reportUrl = 'Please provide a file URL or upload a file';
    }

    if (!formData.duration.trim()) {
      newErrors.duration = 'Please specify the presentation duration';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      // TODO: Implement API call to backend
      console.log('Form submitted:', formData);
      // await submitPresentation(formData);
    } catch (error) {
      console.error('Error submitting form:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInputChange = (field: keyof PresentationFormData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setFormData((prev) => ({
      ...prev,
      [field]: e.target.value,
    }));
    // Clear error when user starts typing
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({
        ...prev,
        [field]: undefined,
      }));
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // TODO: Handle file upload - could convert to data URL or upload to server
      // For now, set the file name as the URL
      setFormData((prev) => ({
        ...prev,
        reportUrl: file.name,
      }));
      // Clear error when file is selected
      if (errors.reportUrl) {
        setErrors((prev) => ({
          ...prev,
          reportUrl: undefined,
        }));
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="glass-card flex flex-col gap-6 rounded-xl p-6 sm:p-8 md:p-10">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col">
          <p className="pb-2 text-base font-medium text-slate-800">Source</p>
          <div className="relative flex w-full items-center">
            <input
              type="text"
              id="report-url"
              name="reportUrl"
              placeholder="Paste a URL or upload a file"
              value={formData.reportUrl}
              onChange={handleInputChange('reportUrl')}
              className={`
                h-14 w-full rounded-lg border border-slate-300 bg-white pl-4 pr-12
                text-base font-normal text-slate-800 placeholder:text-slate-400 
                focus:border-primary-500 focus:outline-0 focus:ring-2 focus:ring-primary-500/50
                ${errors.reportUrl ? 'border-red-500' : ''}
              `}
            />
            <div className="absolute right-2 flex items-center">
              <input
                type="file"
                id="file-upload"
                accept=".pdf,.doc,.docx,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
              <label
                htmlFor="file-upload"
                className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-800 focus:outline-0 focus:ring-2 focus:ring-primary-500/50"
                title="Upload file"
              >
                <Icon
                  name="attach_file"
                  className="text-xl"
                />
              </label>
            </div>
          </div>
          {errors.reportUrl && (
            <p className="mt-1 text-sm text-red-500">{errors.reportUrl}</p>
          )}
        </div>

          <div className="flex flex-col">
            <div className="flex items-center justify-between pb-2">
              <p className="text-base font-medium text-slate-800">Duration</p>
            </div>
            <div className="flex w-full flex-col items-end gap-2">
              <Input
                type="text"
                id="duration"
                name="duration"
                value={formData.duration}
                onChange={handleInputChange('duration')}
                error={errors.duration}
                className="border border-slate-300 w-full"
              />
              <button
                type="button"
                onClick={() => setShowConfig(!showConfig)}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-600 transition-colors hover:text-primary-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 focus-visible:ring-offset-2"
              >
                <Icon
                  name="tune"
                  className={`text-lg transition-transform ${showConfig ? 'rotate-90' : ''}`}
                />
                <span>Customize</span>
              </button>
            </div>
          </div>

        {showConfig && (
          <div className="flex flex-col gap-4 border-t border-slate-200 pt-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Scenario"
                type="text"
                id="scenario"
                name="scenario"
                placeholder="e.g., Academic, Sales"
                value={formData.scenario}
                onChange={handleInputChange('scenario')}
                className="border border-slate-300"
              />
              <Input
                label="Target Audience"
                type="text"
                id="target-audience"
                name="targetAudience"
                placeholder="e.g., Students, Executives"
                value={formData.targetAudience}
                onChange={handleInputChange('targetAudience')}
                className="border border-slate-300"
              />
            </div>
            <Textarea
              label="Custom Instruction"
              id="custom-instruction"
              name="customInstruction"
              placeholder="e.g., Keep slides clean, focus on metrics"
              rows={3}
              value={formData.customInstruction}
              onChange={handleInputChange('customInstruction')}
              className="border border-slate-300"
            />
          </div>
        )}
      </div>

      <Button type="submit" variant="primary" fullWidth disabled={isSubmitting}>
        {isSubmitting ? 'Generating...' : 'Generate Slides'}
      </Button>
    </form>
  );
};

export default PresentationForm;

