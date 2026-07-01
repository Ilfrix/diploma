import { searchApi } from './api';

class SearchService {
  constructor() {
    this.pollingIntervals = new Map(); // Хранилище активных polling интервалов
  }

  /**
   * Синхронный поиск (для обратной совместимости)
   */
  async searchByImage(formData, limit = 10, threshold = 0.7, color = null) {
    const params = { limit, threshold };
    if (color) params.color = color;

    const response = await searchApi.searchSync(formData, params);
    return response.data;
  }

  /**
   * Асинхронный поиск через Kafka с polling
   * @returns {Promise} Результат поиска
   */
  async searchByImageAsync(formData, limit = 10, threshold = 0.7, color = null, options = {}) {
    const {
      maxAttempts = 60,      // Максимум попыток polling
      intervalMs = 2000,     // Интервал между попытками
      onStatusChange = null, // Колбэк для отслеживания статуса
    } = options;

    const params = { limit, threshold };
    if (color) params.color = color;

    // Отправка запроса на асинхронную обработку
    const response = await searchApi.searchAsync(formData, params);
    const { request_id } = response.data;

    // Уведомление об отправке
    if (onStatusChange) {
      onStatusChange({ status: 'queued', requestId: request_id });
    }

    // Polling результата
    const result = await this._pollSearchResult(request_id, maxAttempts, intervalMs, onStatusChange);

    return result;
  }

  /**
   * Polling для получения результата
   * @private
   */
  async _pollSearchResult(requestId, maxAttempts, intervalMs, onStatusChange) {
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const response = await searchApi.getSearchResult(requestId);
        const data = response.data;

        // Уведомление об изменении статуса
        if (onStatusChange) {
          onStatusChange({ status: data.status, requestId });
        }

        // Завершен успешно
        if (data.status === 'processed') {
          return data.result?.similar_images || [];
        }

        // Завершен с ошибкой
        if (data.status === 'failed') {
          throw new Error(data.error || 'Search failed');
        }

        // Истек срок действия
        if (data.status === 'expired') {
          throw new Error('Search request expired');
        }

        await this._delay(intervalMs);
        attempts++;

      } catch (error) {
        if (error.response?.status === 404) {
          await this._delay(intervalMs);
          attempts++;
          continue;
        }
        throw error;
      }
    }

    throw new Error('Search timeout');
  }

  /**
   * Получение результата по request_id (однократно)
   */
  async getSearchResult(requestId) {
    const response = await searchApi.getSearchResult(requestId);
    return response.data;
  }

  /**
   * Получение похожих изображений по ID образца
   */
  async getSimilar(sampleId, limit = 12, threshold = 0.6, color = null) {
    const params = { limit, threshold };
    if (color) params.color = color;

    const response = await searchApi.getSimilar(sampleId, params);
    return response.data;
  }

  /**
   * Отмена активного polling (если нужно)
   */
  cancelPolling(requestId) {
    if (this.pollingIntervals.has(requestId)) {
      clearInterval(this.pollingIntervals.get(requestId));
      this.pollingIntervals.delete(requestId);
    }
  }

  /**
   * Вспомогательная функция для задержки
   * @private
   */
  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Создание и экспорт синглтон
export const searchService = new SearchService();

// Для обратной совместимости с samplesService
export const samplesService = {
  getAll: (params) => searchApi.getSamples(params).then(r => r.data),
  getById: (id) => searchApi.getSample(id).then(r => r.data),
  create: (formData) => searchApi.createSample(formData).then(r => r.data),
  update: (id, data) => searchApi.updateSample(id, data).then(r => r.data),
  delete: (id) => searchApi.deleteSample(id).then(r => r.data),
  getSimilar: (id, limit, threshold, color) => searchService.getSimilar(id, limit, threshold, color),
  searchByImage: (formData, limit, threshold, color) => searchService.searchByImage(formData, limit, threshold, color),
  // Новый асинхронный метод
  searchByImageAsync: (formData, limit, threshold, color, options) =>
    searchService.searchByImageAsync(formData, limit, threshold, color, options),
};
