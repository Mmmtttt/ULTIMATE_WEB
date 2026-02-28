/**
 * 主题配置
 * 定义应用的颜色、字体、间距等样式变量
 */

// 颜色配置
export const COLORS = {
  // 主色调
  PRIMARY: '#1989fa',
  PRIMARY_LIGHT: '#4ca6fb',
  PRIMARY_DARK: '#0f5aa8',
  
  // 成功色
  SUCCESS: '#07c160',
  SUCCESS_LIGHT: '#3dd680',
  SUCCESS_DARK: '#059448',
  
  // 警告色
  WARNING: '#ff976a',
  WARNING_LIGHT: '#ffb896',
  WARNING_DARK: '#cc793f',
  
  // 危险色
  DANGER: '#ee0a24',
  DANGER_LIGHT: '#f1455c',
  DANGER_DARK: '#b30a1d',
  
  // 信息色
  INFO: '#1989fa',
  INFO_LIGHT: '#4ca6fb',
  INFO_DARK: '#0f5aa8',
  
  // 中性色
  GRAY_1: '#323233',
  GRAY_2: '#646566',
  GRAY_3: '#969799',
  GRAY_4: '#c8c9cc',
  GRAY_5: '#ebedf0',
  GRAY_6: '#f2f3f5',
  GRAY_7: '#f7f8fa',
  
  // 背景色
  BACKGROUND: '#f7f8fa',
  BACKGROUND_DARK: '#1a1a1a',
  BACKGROUND_EYE: '#c7edcc',
  
  // 文字色
  TEXT_PRIMARY: '#323233',
  TEXT_SECONDARY: '#646566',
  TEXT_TERTIARY: '#969799',
  TEXT_LINK: '#1989fa',
  
  // 边框色
  BORDER: '#ebedf0',
  BORDER_DARK: '#3a3a3c'
}

// 阅读器背景色
export const READER_BACKGROUNDS = {
  WHITE: {
    name: '白色',
    color: '#ffffff',
    textColor: '#323233'
  },
  DARK: {
    name: '深色',
    color: '#1a1a1a',
    textColor: '#ebedf0'
  },
  EYE_PROTECTION: {
    name: '护眼色',
    color: '#c7edcc',
    textColor: '#323233'
  }
}

// 字体配置
export const FONTS = {
  // 字体族
  FAMILY: {
    BASE: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    MONO: '"SF Mono", Monaco, Inconsolata, "Lucida Console", monospace'
  },
  
  // 字体大小
  SIZE: {
    XS: '10px',
    SM: '12px',
    MD: '14px',
    LG: '16px',
    XL: '18px',
    XXL: '20px',
    XXXL: '24px'
  },
  
  // 字重
  WEIGHT: {
    NORMAL: 400,
    MEDIUM: 500,
    BOLD: 600,
    BOLDER: 700
  },
  
  // 行高
  LINE_HEIGHT: {
    TIGHT: 1.2,
    NORMAL: 1.5,
    LOOSE: 1.8
  }
}

// 间距配置
export const SPACING = {
  XS: '4px',
  SM: '8px',
  MD: '12px',
  LG: '16px',
  XL: '20px',
  XXL: '24px',
  XXXL: '32px'
}

// 圆角配置
export const BORDER_RADIUS = {
  SM: '2px',
  MD: '4px',
  LG: '8px',
  XL: '12px',
  ROUND: '50%'
}

// 阴影配置
export const SHADOWS = {
  SM: '0 1px 2px rgba(0, 0, 0, 0.05)',
  MD: '0 2px 8px rgba(0, 0, 0, 0.1)',
  LG: '0 4px 16px rgba(0, 0, 0, 0.15)',
  XL: '0 8px 32px rgba(0, 0, 0, 0.2)'
}

// 过渡配置
export const TRANSITIONS = {
  FAST: 'all 0.15s ease',
  NORMAL: 'all 0.3s ease',
  SLOW: 'all 0.5s ease'
}

// 断点配置（响应式）
export const BREAKPOINTS = {
  XS: '320px',
  SM: '576px',
  MD: '768px',
  LG: '992px',
  XL: '1200px',
  XXL: '1400px'
}

// Z-index 配置
export const Z_INDEX = {
  BASE: 0,
  DROPDOWN: 1000,
  STICKY: 1020,
  FIXED: 1030,
  MODAL_BACKDROP: 1040,
  MODAL: 1050,
  POPOVER: 1060,
  TOOLTIP: 1070,
  TOAST: 1080
}

// 导出默认主题
export const DEFAULT_THEME = {
  colors: COLORS,
  backgrounds: READER_BACKGROUNDS,
  fonts: FONTS,
  spacing: SPACING,
  borderRadius: BORDER_RADIUS,
  shadows: SHADOWS,
  transitions: TRANSITIONS,
  breakpoints: BREAKPOINTS,
  zIndex: Z_INDEX
}
