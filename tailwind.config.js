/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'brand-navy': '#084A79',
        'brand-red': '#EB5134',
        'brand-yellow': '#F4A222',
        'brand-teal': '#10857E',
        'brand-cream': '#F8F5EE',
      },
    },
  },
  plugins: [],
}
