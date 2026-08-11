/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        // 护理工作站 token（与 src/styles/theme.css 保持一致）
        med: {
          bg: '#eeebe5',
          surface: '#fffdfa',
          'surface-2': '#f6f3ee',
          border: '#d9d3ca',
          primary: '#147976',
          'primary-light': '#2a9994',
          text: '#1b2a2e',
          'text-2': '#536367',
          'text-3': '#8a9796',
          success: '#18835e',
          warning: '#bd762b',
          danger: '#c85b50',
          info: '#718083'
        }
      },
      fontFamily: {
        sans: ['Inter', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        num: ['Outfit', 'Inter', 'sans-serif']
      },
      boxShadow: {
        card: '0 10px 28px rgba(39, 48, 48, 0.075)',
        'card-hover': '0 14px 34px rgba(39, 48, 48, 0.13)'
      }
    }
  },
  plugins: []
}
