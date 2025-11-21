import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  className = '',
  ...props
}) => {
  return (
    <label className="flex w-full flex-col">
      {label && (
        <p className="pb-2 text-base font-medium text-slate-800">{label}</p>
      )}
      <div className="flex w-full flex-1 items-stretch rounded-lg">
        <input
          className={`
            form-input h-14 w-full flex-1 resize-none rounded-lg border-slate-300 bg-white p-4 
            text-base font-normal text-slate-800 placeholder:text-slate-400 
            focus:border-primary-500 focus:outline-0 focus:ring-2 focus:ring-primary-500/50
            ${error ? 'border-red-500' : ''}
            ${className}
          `}
          {...props}
        />
      </div>
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
      {helperText && !error && <p className="mt-1 text-sm text-slate-500">{helperText}</p>}
    </label>
  );
};

export default Input;

