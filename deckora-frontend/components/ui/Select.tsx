import React from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
  placeholder?: string;
}

const Select: React.FC<SelectProps> = ({
  label,
  options,
  error,
  helperText,
  placeholder,
  className = '',
  value,
  ...props
}) => {
  const showPlaceholder = placeholder && (!value || value === '');
  
  return (
    <label className="flex flex-col">
      {label && (
        <p className="pb-2 text-base font-medium text-slate-800">{label}</p>
      )}
      <select
        id={props.id || props.name}
        name={props.name}
        className={`
          form-select h-14 w-full flex-1 resize-none appearance-none rounded-lg 
          border-slate-300 bg-white p-4 text-base font-normal text-slate-800 
          focus:border-primary-500 focus:outline-0 focus:ring-2 focus:ring-primary-500/50
          ${error ? 'border-red-500' : ''}
          ${showPlaceholder ? 'text-slate-400' : 'text-slate-800'}
          ${className}
        `}
        style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")',
          backgroundPosition: 'right 0.75rem center',
          backgroundRepeat: 'no-repeat',
          backgroundSize: '1.5em 1.5em',
          paddingRight: '2.5rem',
        }}
        value={value}
        {...props}
      >
        {placeholder && (
          <option value="" disabled hidden>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
      {helperText && !error && <p className="mt-1 text-sm text-slate-500">{helperText}</p>}
    </label>
  );
};

export default Select;

