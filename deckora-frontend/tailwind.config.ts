import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#7C3AED',
          50: '#F5F3FF',
          100: '#EDE9FE',
          500: '#7C3AED',
          600: '#6D28D9',
          700: '#5B21B6',
        },
        secondary: {
          DEFAULT: '#EC4899',
          500: '#EC4899',
        },
      },
      fontFamily: {
        display: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.75rem',
        lg: '1rem',
        xl: '1.5rem',
        full: '9999px',
      },
    },
  },
  plugins: [],
}
export default config

