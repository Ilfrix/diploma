// API конфигурация
export const API_CONFIG = {
  BASE_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
  TIMEOUT: 30000,
  RETRY_COUNT: 2,
  RETRY_DELAY: 1000,
};

// Настройки изображений
export const IMAGE_CONFIG = {
  MAX_SIZE_MB: 10,
  MAX_SIZE_BYTES: 10 * 1024 * 1024,
  ALLOWED_TYPES: ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'],
  ALLOWED_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
  PREVIEW_QUALITY: 0.8,
  THUMBNAIL_SIZE: {
    width: 300,
    height: 300,
  },
};

// Настройки поиска
export const SEARCH_CONFIG = {
  DEFAULT_LIMIT: 10,
  DEFAULT_THRESHOLD: 0.7,
  MIN_THRESHOLD: 0.1,
  MAX_THRESHOLD: 1.0,
  THRESHOLD_STEP: 0.05,
  LIMIT_MIN: 1,
  LIMIT_MAX: 100,
};

// Настройки пагинации
export const PAGINATION_CONFIG = {
  DEFAULT_PAGE_SIZE: 12,
  PAGE_SIZE_OPTIONS: [12, 24, 48, 96],
  DEFAULT_PAGE: 0,
};

// Сообщения об ошибках
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Ошибка сети. Проверьте подключение к интернету.',
  UNAUTHORIZED: 'Необходимо авторизоваться',
  FORBIDDEN: 'Доступ запрещен',
  NOT_FOUND: 'Ресурс не найден',
  SERVER_ERROR: 'Ошибка сервера. Попробуйте позже.',
  VALIDATION_ERROR: 'Проверьте правильность заполнения полей',
  FILE_TOO_LARGE: `Файл слишком большой. Максимальный размер: ${IMAGE_CONFIG.MAX_SIZE_MB}MB`,
  FILE_TYPE_NOT_ALLOWED: `Неподдерживаемый тип файла. Разрешены: ${IMAGE_CONFIG.ALLOWED_TYPES.join(', ')}`,
  DUPLICATE_IMAGE: 'Такое изображение уже существует в системе',
  SAMPLE_NOT_FOUND: 'Эталон не найден',
};

// Успешные сообщения
export const SUCCESS_MESSAGES = {
  LOGIN_SUCCESS: 'Вход выполнен успешно!',
  REGISTER_SUCCESS: 'Регистрация успешна!',
  LOGOUT_SUCCESS: 'Вы вышли из системы',
  SAMPLE_CREATED: 'Эталон успешно создан',
  SAMPLE_UPDATED: 'Эталон успешно обновлен',
  SAMPLE_DELETED: 'Эталон удален',
  IMAGE_UPLOADED: 'Изображение загружено',
  SEARCH_PROCESSED: 'Поиск завершен',
};

// URL маршруты
export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  SAMPLES: '/samples',
  SAMPLE_CREATE: '/samples/create',
  SAMPLE_EDIT: (id) => `/samples/${id}/edit`,
  SAMPLE_DETAIL: (id) => `/samples/${id}`,
  SEARCH: '/search',
};

// API эндпоинты
export const API_ENDPOINTS = {
  REGISTER: '/register',
  LOGIN: '/login',
  SAMPLES: '/samples',
  SAMPLE_BY_ID: (id) => `/samples/${id}`,
  SAMPLE_SIMILAR: (id) => `/samples/${id}/similar`,
  SEARCH_SIMILAR: '/search/similar',
  HEALTH: '/health',
};

// Ключи для React Query
export const QUERY_KEYS = {
  USER: 'user',
  SAMPLES: 'samples',
  SAMPLE: (id) => ['sample', id],
  SIMILAR: (id) => ['similar', id],
  SEARCH_RESULTS: 'searchResults',
};

// Настройки аутентификации
export const AUTH_CONFIG = {
  TOKEN_KEY: 'access_token',
  USER_KEY: 'user',
  TOKEN_EXPIRY_BUFFER: 5 * 60, // 5 minutes in seconds
};

// UI настройки
export const UI_CONFIG = {
  TOAST_DURATION: 4000,
  DEBOUNCE_DELAY: 500,
  ANIMATION_DURATION: 300,
  LOADER_SIZE: {
    SMALL: 24,
    MEDIUM: 48,
    LARGE: 64,
  },
};

// Форматы дат
export const DATE_FORMATS = {
  FULL: 'dd MMMM yyyy, HH:mm',
  DATE_ONLY: 'dd MMMM yyyy',
  TIME_ONLY: 'HH:mm',
  RELATIVE: 'relative',
};

// Цветовая схема
export const COLORS = {
  PRIMARY: '#3B82F6', // blue-600
  SECONDARY: '#6B7280', // gray-500
  SUCCESS: '#10B981', // green-500
  DANGER: '#EF4444', // red-500
  WARNING: '#F59E0B', // amber-500
  INFO: '#3B82F6', // blue-500
};

// Регулярные выражения для валидации
export const VALIDATION_PATTERNS = {
  EMAIL: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
  USERNAME: /^[a-zA-Z0-9_-]{3,50}$/,
  PASSWORD: /^.{6,}$/,
};

// MIME типы
export const MIME_TYPES = {
  JPEG: 'image/jpeg',
  PNG: 'image/png',
  GIF: 'image/gif',
  BMP: 'image/bmp',
  WEBP: 'image/webp',
};

// Локальные настройки
export const LOCALE = {
  LANGUAGE: 'ru',
  DATE_LOCALE: 'ru',
  TIMEZONE: 'Europe/Moscow',
};

// Настройки производительности
export const PERFORMANCE_CONFIG = {
  IMAGE_LAZY_LOAD_THRESHOLD: 200, // pixels
  DEBOUNCE_SEARCH: 300, // ms
  THROTTLE_SCROLL: 100, // ms
  MAX_CONCURRENT_UPLOADS: 3,
};

// Уровни логирования
export const LOG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
};

// Функции-помощники для работы с константами
export const getImageUrl = (path) => {
  if (!path) return '/placeholder-image.jpg';
  if (path.startsWith('http')) return path;
  return `${API_CONFIG.BASE_URL.replace('/api', '')}/${path}`;
};

export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const getSimilarityColor = (score) => {
  if (score >= 0.8) return COLORS.SUCCESS;
  if (score >= 0.6) return COLORS.INFO;
  if (score >= 0.4) return COLORS.WARNING;
  return COLORS.DANGER;
};

export const getSimilarityLabel = (score) => {
  if (score >= 0.9) return 'Почти идентично';
  if (score >= 0.8) return 'Очень похоже';
  if (score >= 0.7) return 'Похоже';
  if (score >= 0.6) return 'Умеренно похоже';
  if (score >= 0.5) return 'Слабо похоже';
  return 'Не похоже';
};