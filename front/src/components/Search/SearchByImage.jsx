import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { samplesService } from '../../services/samples';
import { useDropzone } from 'react-dropzone';
import SimilarImages from './SimilarImages';
import Loader from '../Common/Loader';
import { FiUpload, FiSearch } from 'react-icons/fi';
import { IoColorPalette, IoTimeOutline, IoCheckmarkCircle } from 'react-icons/io5';
import toast from 'react-hot-toast';

// Цветовая палитра
const COLOR_PALETTE = {
  "red": { name: "Красный", rgb: [180, 40, 40], category: "Основные" },
  "green": { name: "Зеленый", rgb: [40, 160, 40], category: "Основные" },
  "blue": { name: "Синий", rgb: [40, 40, 160], category: "Основные" },
  "black": { name: "Черный", rgb: [10, 10, 10], category: "Нейтральные" },
  "white": { name: "Белый", rgb: [240, 240, 240], category: "Нейтральные" },
  "gray": { name: "Серый", rgb: [120, 120, 120], category: "Нейтральные" },
};

// Компонент Tooltip
const ColorNameTooltip = ({ colorName, rgb, isVisible, mousePos }) => {
  if (!isVisible || !mousePos) return null;

  return (
    <div
      className="fixed z-[9999] pointer-events-none"
      style={{
        left: `${mousePos.x + 20}px`,
        top: `${mousePos.y - 70}px`,
        width: '150px',
        height: 'auto',
      }}
    >
      <div
        className="rounded-lg shadow-2xl overflow-hidden border border-white/20"
        style={{ backgroundColor: `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})` }}
      >
        <div className="px-3 py-2">
          <div className="text-xs font-semibold text-center text-white drop-shadow-md">
            {colorName}
          </div>
          <div className="text-[10px] text-center text-white/90 font-mono drop-shadow-md mt-0.5">
            RGB({rgb[0]}, {rgb[1]}, {rgb[2]})
          </div>
        </div>
      </div>
    </div>
  );
};

// Компонент для отображения цвета
const ColorSwatch = ({ color, rgb, isSelected, onClick }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [mousePos, setMousePos] = useState(null);

  const handleMouseMove = (e) => {
    if (isHovered) {
      setMousePos({ x: e.clientX, y: e.clientY });
    }
  };

  return (
    <div
      className="relative flex flex-col items-center cursor-pointer transition-all duration-200"
      onClick={onClick}
      onMouseEnter={(e) => {
        setIsHovered(true);
        setMousePos({ x: e.clientX, y: e.clientY });
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => {
        setIsHovered(false);
        setMousePos(null);
      }}
    >
      <ColorNameTooltip
        colorName={color}
        rgb={rgb}
        isVisible={isHovered}
        mousePos={mousePos}
      />

      <div
        className={`w-10 h-10 rounded-full border-2 transition-all ${
          isSelected
            ? 'transform scale-105 border-blue-500 ring-2 ring-blue-200'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        style={{ backgroundColor: `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})` }}
      />

      <span
        className={`text-xs mt-1 text-center cursor-help ${
          isSelected ? 'text-blue-600 font-medium' : 'text-gray-600'
        }`}
      >
        {color}
      </span>
    </div>
  );
};

// Отдельная группа цветов
const ColorGroup = ({ title, colors, selectedColor, onColorSelect }) => {
  if (colors.length === 0) return null;
  
  return (
    <div className="mb-6">
      <h4 className="text-sm font-medium text-gray-500 mb-2 sticky top-0 bg-gray-50 py-1">
        {title}
      </h4>
      <div className="flex flex-wrap gap-2">
        {colors.map(([key, data]) => (
          <ColorSwatch
            key={key}
            color={data.name}
            rgb={data.rgb}
            isSelected={selectedColor === key}
            onClick={() => onColorSelect(selectedColor === key ? null : key)}
          />
        ))}
      </div>
    </div>
  );
};

const SearchByImage = () => {
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [requestId, setRequestId] = useState(null);
  const [searchStatus, setSearchStatus] = useState(null);
  const [limit, setLimit] = useState(10);
  const [threshold, setThreshold] = useState(0.7);
  const [selectedColor, setSelectedColor] = useState(null);
  const [showColorFilter, setShowColorFilter] = useState(false);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.bmp']
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      const file = acceptedFiles[0];
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
      setSearchResults(null);
      setRequestId(null);
      setSearchStatus(null);
    }
  });

  // Асинхронный поиск через Kafka
  const asyncSearchMutation = useMutation(
    (formData) => samplesService.searchByImageAsync(formData, limit, threshold, selectedColor, {
      onStatusChange: ({ status, requestId: reqId }) => {
        setRequestId(reqId);
        setSearchStatus(status);
        if (status === 'queued') {
          toast.success('Запрос поставлен в очередь');
        } else if (status === 'processing') {
          toast('Обработка изображения...', { icon: '⏳' });
        }
      }
    }),
    {
      onSuccess: (data) => {
        setSearchResults(data);
        setSearchStatus('processed');
        if (data.length === 0) {
          toast(selectedColor ? `Изображений цвета "${COLOR_PALETTE[selectedColor]?.name}" не найдено` : 'Похожих изображений не найдено', 
            { icon: '🔍' });
        } else {
          toast.success(`Найдено ${data.length} похожих изображений`);
        }
      },
      onError: (error) => {
        toast.error(error.message || 'Ошибка поиска');
        setSearchStatus('failed');
      }
    }
  );

  const handleSearch = async () => {
    if (!imageFile) {
      toast.error('Выберите изображение');
      return;
    }

    setSearchResults(null);
    setRequestId(null);
    setSearchStatus(null);

    const formData = new FormData();
    formData.append('image', imageFile);
    
    await asyncSearchMutation.mutateAsync(formData);
  };

  const handleClear = () => {
    setImageFile(null);
    setImagePreview(null);
    setSearchResults(null);
    setRequestId(null);
    setSearchStatus(null);
    setSelectedColor(null);
  };

  const isLoading = asyncSearchMutation.isLoading;

  const getStatusDisplay = () => {
    if (!searchStatus) return null;
    
    switch (searchStatus) {
      case 'queued':
        return { text: 'В очереди...', icon: <IoTimeOutline className="w-4 h-4" />, color: 'text-yellow-600' };
      case 'processing':
        return { text: 'Обработка...', icon: <Loader size="small" />, color: 'text-blue-600' };
      case 'processed':
        return { text: 'Готово!', icon: <IoCheckmarkCircle className="w-4 h-4" />, color: 'text-green-600' };
      case 'failed':
        return { text: 'Ошибка', icon: null, color: 'text-red-600' };
      default:
        return null;
    }
  };

  const statusDisplay = getStatusDisplay();

  // Подготовка данных для левой колонки
  const leftColumnData = [
    { title: "Основные", colors: Object.entries(COLOR_PALETTE).filter(([_, data]) => data.category === "Основные") },
  ];

  const rightColumnData = [
    { title: "Нейтральные", colors: Object.entries(COLOR_PALETTE).filter(([_, data]) => data.category === "Нейтральные") },
  ];

  const selectedColorData = selectedColor ? COLOR_PALETTE[selectedColor] : null;
  const selectedColorRgb = selectedColorData?.rgb;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Поиск по изображению</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Левая колонка - форма загрузки */}
        <div className="card p-6">
          <h2 className="text-xl font-semibold mb-4">Загрузите изображение</h2>
          
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors mb-4
              ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-500'}`}
          >
            <input {...getInputProps()} />
            <FiUpload className="mx-auto text-4xl text-gray-400 mb-2" />
            {isDragActive ? (
              <p>Отпустите файл здесь...</p>
            ) : (
              <p>Перетащите изображение или кликните для выбора</p>
            )}
          </div>
          
          {imagePreview && (
            <div className="mb-4">
              <img src={imagePreview} alt="Preview" className="max-h-64 mx-auto rounded-lg" />
              <button
                onClick={handleClear}
                className="mt-2 text-red-600 hover:text-red-700 text-sm"
              >
                Удалить
              </button>
            </div>
          )}
          
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-gray-700">Максимум результатов: {limit}</label>
              </div>
              <input
                type="range"
                min="1"
                max="50"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                className="w-full"
              />
            </div>
            
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-gray-700">Порог схожести: {threshold}</label>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Цветовой фильтр */}
            <div className="border-t pt-4">
              <button
                onClick={() => setShowColorFilter(!showColorFilter)}
                className="flex items-center gap-2 text-gray-600 hover:text-blue-600 transition-colors mb-3"
              >
                <IoColorPalette className="text-xl" />
                <span className="font-medium">Фильтр по цвету</span>
                <span className={`text-xs transform transition-transform ${showColorFilter ? 'rotate-180' : ''}`}>
                  ▼
                </span>
              </button>
              
              {showColorFilter && (
                <div className="bg-gray-50 rounded-lg p-3 mb-2">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      {selectedColor && selectedColorRgb ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div
                            style={{
                              width: '44px',
                              height: '44px',
                              backgroundColor: `rgb(${selectedColorRgb[0]}, ${selectedColorRgb[1]}, ${selectedColorRgb[2]})`,
                              borderRadius: '6px',
                              border: selectedColor === 'white' ? '1px solid #ccc' : 'none',
                              boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                            }}
                          />
                          <div>
                            <div style={{ fontWeight: '500', fontSize: '14px', color: '#333' }}>
                              {selectedColorData?.name}
                            </div>
                            <div style={{ fontSize: '11px', color: '#666', fontFamily: 'monospace' }}>
                              RGB({selectedColorRgb[0]}, {selectedColorRgb[1]}, {selectedColorRgb[2]})
                            </div>
                          </div>
                        </div>
                      ) : (
                        <span className="text-sm text-gray-500">Цвет не выбран</span>
                      )}
                    </div>
                    {selectedColor && (
                      <button
                        onClick={() => setSelectedColor(null)}
                        className="text-xs text-red-500 hover:text-red-600"
                      >
                        Сбросить
                      </button>
                    )}
                  </div>
                  
                  {/* Две колонки */}
                  <div style={{ display: 'flex', gap: '16px' }}>
                    <div style={{ flex: 1 }}>
                      {leftColumnData.map(group => (
                        <ColorGroup
                          key={group.title}
                          title={group.title}
                          colors={group.colors}
                          selectedColor={selectedColor}
                          onColorSelect={setSelectedColor}
                        />
                      ))}
                    </div>
                    <div style={{ flex: 1 }}>
                      {rightColumnData.map(group => (
                        <ColorGroup
                          key={group.title}
                          title={group.title}
                          colors={group.colors}
                          selectedColor={selectedColor}
                          onColorSelect={setSelectedColor}
                        />
                      ))}
                    </div>
                  </div>
                  
                  <p className="text-xs text-gray-400 mt-3 pt-2 border-t">
                    Наведите на название цвета, чтобы увидеть оттенок
                  </p>
                </div>
              )}
            </div>
            
            <button
              onClick={handleSearch}
              disabled={!imageFile || isLoading}
              className="btn-primary w-full inline-flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader size="small" />
                  <span>Отправка...</span>
                </>
              ) : (
                <>
                  <FiSearch />
                  Найти похожие
                </>
              )}
            </button>
            
            {/* Индикатор статуса */}
            {statusDisplay && (
              <div className={`mt-3 p-2 rounded-lg text-center ${
                searchStatus === 'processed' ? 'bg-green-50' : 'bg-blue-50'
              }`}>
                <div className={`flex items-center justify-center gap-2 ${statusDisplay.color}`}>
                  {statusDisplay.icon}
                  <span className="text-sm">{statusDisplay.text}</span>
                </div>
                {requestId && searchStatus !== 'processed' && searchStatus !== 'failed' && (
                  <p className="text-xs text-gray-500 mt-1">
                    ID: {requestId.slice(0, 8)}...
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
        
        {/* Правая колонка - результаты */}
        <div>
          {searchResults ? (
            <SimilarImages
              similarImages={searchResults}
              title={`Результаты поиска${selectedColor ? ` (цвет: ${selectedColorData?.name || selectedColor})` : ''}`}
            />
          ) : searchStatus === 'processing' ? (
            <div className="card p-8 text-center">
              <Loader />
              <p className="mt-4 text-gray-600">Обработка изображения в очереди...</p>
              <p className="text-sm text-gray-400 mt-2">Это может занять до 30 секунд</p>
            </div>
          ) : (
            <div className="card p-8 text-center text-gray-400">
              <FiSearch className="mx-auto text-4xl mb-2" />
              <p>Результаты поиска появятся здесь</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchByImage;