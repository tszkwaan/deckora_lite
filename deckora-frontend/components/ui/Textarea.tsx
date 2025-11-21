import React from 'react';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  helperText,
  className = '',
  ...props
}) => {
  return (
    <label className="flex flex-col">
      {label && (
        <p className="pb-2 text-base font-medium text-slate-800">{label}</p>
      )}
      <textarea
        className={`
          form-textarea w-full flex-1 resize-none rounded-lg border-slate-300 bg-white p-4 
          text-base font-normal text-slate-800 placeholder:text-slate-400 
          focus:border-primary-500 focus:outline-0 focus:ring-2 focus:ring-primary-500/50
          ${error ? 'border-red-500' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
      {helperText && !error && <p className="mt-1 text-sm text-slate-500">{helperText}</p>}
    </label>
  );
};

export default Textarea;

