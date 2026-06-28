module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,md,mdx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './lib/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        studio: {
          paper: '#FAFAF8',
          ink: '#141413',
          muted: '#66645F',
          line: '#E6E2D9',
          accent: '#2563EB',
          soft: '#F0EFEA',
        },
      },
    },
  },
  plugins: [],
}
