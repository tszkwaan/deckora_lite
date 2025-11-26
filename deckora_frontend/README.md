# Deckora Frontend

A Next.js frontend application for Deckora - Transform Reports into Presentations.

## Features

- Modern, responsive UI built with Next.js 14 and Tailwind CSS
- Type-safe components using TypeScript
- Reusable component architecture following SOLID principles
- Form validation and error handling
- Accessible components with proper ARIA labels

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
npm install
```

### Environment Setup

1. Create a `.env.local` file in the `deckora_frontend` directory:

```bash
cp .env.example .env.local
```

2. Update `.env.local` with your API URL:

```env
NEXT_PUBLIC_API_URL=YOUR_CLOUD_RUN_APP_URL
```

**Note**: `.env.local` is already in `.gitignore` and will not be committed to version control.

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
npm run build
npm start
```

## Project Structure

```
deckora_frontend/
├── app/                    # Next.js app directory
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   └── globals.css        # Global styles
├── components/
│   ├── ui/                # Reusable UI components
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Select.tsx
│   │   ├── Textarea.tsx
│   │   └── Icon.tsx
│   ├── layout/            # Layout components
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   ├── Hero.tsx
│   │   └── Features.tsx
│   └── forms/             # Form components
│       └── PresentationForm.tsx
├── lib/                   # Utility functions and constants
│   └── constants.ts
├── types/                 # TypeScript type definitions
│   └── index.ts
└── public/               # Static assets
```

## Architecture

### SOLID Principles

- **Single Responsibility**: Each component has a single, well-defined purpose
- **Open/Closed**: Components are extensible through props without modification
- **Liskov Substitution**: Components can be replaced with their subtypes
- **Interface Segregation**: Components expose only necessary props
- **Dependency Inversion**: Components depend on abstractions (props) not concrete implementations

### Component Design

- **UI Components**: Reusable, presentational components with no business logic
- **Layout Components**: Structural components for page layout
- **Form Components**: Container components that handle form state and validation
- **Type Safety**: All components are fully typed with TypeScript

## Technologies

- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS**: Utility-first CSS framework
- **React**: UI library

## License

MIT
