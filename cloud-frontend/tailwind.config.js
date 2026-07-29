/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        // 医疗蓝浅色主题 token
        med: {
          bg: '#f0f5ff',
          surface: '#ffffff',
          'surface-2': '#f5f9ff',
          border: '#d6e4ff',
          primary: '#1677ff',
          'primary-light': '#4096ff',
          text: '#1d2129',
          'text-2': '#4e5969',
          'text-3': '#86909c',
          success: '#00b42a',
          warning: '#ff7d00',
          danger: '#f53f3f',
          info: '#86909c'
        }
      },
      fontFamily: {
        sans: ['Inter', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        num: ['Outfit', 'Inter', 'sans-serif']
      },
      boxShadow: {
        card: '0 1px 4px rgba(22, 119, 255, 0.08)',
        'card-hover': '0 4px 12px rgba(22, 119, 255, 0.15)'
      }
    }
  },
  plugins: []
}
