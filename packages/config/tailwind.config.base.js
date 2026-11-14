/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f2f7f4',
          100: '#d9ebdd',
          200: '#b3d7be',
          300: '#82bd97',
          400: '#4f9e71',
          500: '#287a5a', // Secondary green
          600: '#1f6349',
          700: '#173d32', // Forest green
          800: '#112c24',
          900: '#0c1e19',
          950: '#07120f',
        },
        forest: {
          DEFAULT: '#173D32',
          dark: '#0F2922',
          light: '#287A5A',
        },
        warm: {
          50: '#FAF8F5',
          100: '#F5F2EA', // Warm off-white
          200: '#EBE6D8',
          300: '#DDD5C2',
          400: '#C8BEA7',
        },
        charcoal: {
          DEFAULT: '#252B29',
          light: '#3F4744',
          muted: '#66736F',
        },
        match: {
          high: '#287A5A',
          medium: '#D97706',
          low: '#DC2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
