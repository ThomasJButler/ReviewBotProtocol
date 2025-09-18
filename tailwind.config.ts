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
        'matrix-green': '#00ff00',
        'matrix-cyan': '#00ffff',
        'deep-black': '#0a0a0a',
        'card-surface': '#1a1a1a',
        border: 'rgba(255, 255, 255, 0.1)',
        input: 'rgba(26, 26, 26, 0.8)',
        ring: '#00ff00',
        background: '#0a0a0a',
        foreground: '#ffffff',
        primary: {
          DEFAULT: '#00ff00',
          foreground: '#000000',
        },
        secondary: {
          DEFAULT: '#1a1a1a',
          foreground: '#ffffff',
        },
        destructive: {
          DEFAULT: '#ff3333',
          foreground: '#ffffff',
        },
        muted: {
          DEFAULT: '#1a1a1a',
          foreground: '#a0a0a0',
        },
        accent: {
          DEFAULT: '#1a1a1a',
          foreground: '#00ffff',
        },
        popover: {
          DEFAULT: '#1a1a1a',
          foreground: '#ffffff',
        },
        card: {
          DEFAULT: 'rgba(26, 26, 26, 0.6)',
          foreground: '#ffffff',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':
          'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        glass:
          'linear-gradient(135deg, rgba(26, 26, 26, 0.6), rgba(15, 15, 15, 0.8))',
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        'scale-in': 'scaleIn 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'slide-in-left': 'slideInLeft 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        shimmer: 'shimmer 2s infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(0.9)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        slideInLeft: {
          from: { opacity: '0', transform: 'translateX(-30px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/typography')],
}

export default config
