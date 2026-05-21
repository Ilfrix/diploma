import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { samplesService } from '../../services/samples';
import { useDropzone } from 'react-dropzone';
import SimilarImages from './SimilarImages';
import Loader from '../Common/Loader';
import { FiUpload, FiSearch, FiFilter } from 'react-icons/fi';
import { IoColorPalette } from 'react-icons/io5';
import toast from 'react-hot-toast';

// Цветовая палитра
const COLOR_PALETTE = {
  "red": { name: "Красный", rgb: [255, 0, 0], category: "Основные" },
  "green": { name: "Зеленый", rgb: [0, 255, 0], category: "Основные" },
  "blue": { name: "Синий", rgb: [0, 0, 255], category: "Основные" },
  "yellow": { name: "Желтый", rgb: [255, 255, 0], category: "Основные" },
  "purple": { name: "Фиолетовый", rgb: [128, 0, 128], category: "Основные" },
  "orange": { name: "Оранжевый", rgb: [255, 165, 0], category: "Основные" },
  "pink": { name: "Розовый", rgb: [255, 192, 203], category: "Пастельные" },
  "brown": { name: "Коричневый", rgb: [139, 69, 19], category: "Древесные" },
  "black": { name: "Черный", rgb: [0, 0, 0], category: "Нейтральные" },
  "white": { name: "Белый", rgb: [255, 255, 255], category: "Нейтральные" },
  "gray": { name: "Серый", rgb: [128, 128, 128], category: "Нейтральные" },
  "silver": { name: "Серебристый", rgb: [192, 192, 192], category: "Металлик" },
  "beige": { name: "Бежевый", rgb: [245, 245, 220], category: "Нейтральные" },
  "cream": { name: "Кремовый", rgb: [255, 255, 204], category: "Нейтральные" },
  "ivory": { name: "Слоновая кость", rgb: [255, 255, 240], category: "Нейтральные" },
  "wenge": { name: "Венге", rgb: [50, 40, 35], category: "Древесные" },
  "oak": { name: "Дуб", rgb: [160, 120, 80], category: "Древесные" },
  "walnut": { name: "Орех", rgb: [119, 85, 61], category: "Древесные" },
  "cherry": { name: "Вишня", rgb: [138, 54, 15], category: "Древесные" },
  "beech": { name: "Бук", rgb: [196, 160, 116], category: "Древесные" },
  "ash": { name: "Ясень", rgb: [138, 129, 111], category: "Древесные" },
  "pine": { name: "Сосна", rgb: [227, 194, 140], category: "Древесные" },
  "mahogany": { name: "Красное дерево", rgb: [76, 38, 24], category: "Древесные" },
  "gold": { name: "Золотистый", rgb: [255, 215, 0], category: "Металлик" },
  "bronze": { name: "Бронзовый", rgb: [205, 127, 50], category: "Металлик" },
  "copper": { name: "Медный", rgb: [184, 115, 51], category: "Металлик" },
  "taupe": { name: "Серо-коричневый", rgb: [72, 60, 50], category: "Нейтральные" },
  "mint": { name: "Мятный", rgb: [152, 255, 152], category: "Пастельные" },
  "lavender": { name: "Лавандовый", rgb: [230, 230, 250], category: "Пастельные" },
  "turquoise": { name: "Бирюзовый", rgb: [64, 224, 208], category: "Основные" },
  "coral": { name: "Коралловый", rgb: [255, 127, 80], category: "Пастельные" },
  "burgundy": { name: "Бордовый", rgb: [128, 0, 32], category: "Основные" },
  "olive": { name: "Оливковый", rgb: [128, 128, 0], category: "Основные" },
  "khaki": { name: "Хаки", rgb: [195, 176, 145], category: "Нейтральные" },
  "charcoal": { name: "Темно-серый", rgb: [54, 69, 79], category: "Нейтральные" }
};

// Компонент для отображения цвета
const ColorSwatch = ({ color, rgb, isSelected, onClick }) => {
  const [isHovered, setIsHovered] = useState(false);
  
  return (
    <div
      className={`relative flex flex-col items-center cursor-pointer transition-all duration-200 ${
        isSelected ? 'transform scale-105' : ''
      }`}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className={`w-10 h-10 rounded-full border-2 transition-all ${
          isSelected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-300 hover:border-gray-400'
        }`}
        style={{ backgroundColor: `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})` }}
      />
      <span className={`text-xs mt-1 text-center ${isSelected ? 'text-blue-600 font-medium' : 'text-gray-600'}`}>
        {color}
      </span>
    </div>
  );
};

// Группа цветов по категориям
const ColorGroup = ({ title, colors, selectedColor, onColorSelect }) => {
  const groupColors = Object.entries(COLOR_PALETTE).filter(([_, data]) => data.category === title);
  
  if (groupColors.length === 0) return null;
  
  return (
    <div className="mb-4">
      <h4 className="text-sm font-medium text-gray-500 mb-2">{title}</h4>
      <div className="grid grid-cols-6 gap-2">
        {groupColors.map(([key, data]) => (
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
    }
  });

  const searchMutation = useMutation(
    (formData) => samplesService.searchByImage(formData, limit, threshold, selectedColor),
    {
      onSuccess: (data) => {
        setSearchResults(data);
        if (data.length === 0) {
          toast(selectedColor ? `Изображений цвета "${COLOR_PALETTE[selectedColor]?.name}" не найдено` : 'Похожих изображений не найдено', 
            { icon: '🔍' });
        } else {
          toast.success(`Найдено ${data.length} похожих изображений`);
        }
      },
      onError: (error) => {
        toast.error(error.response?.data?.detail || 'Ошибка поиска');
      }
    }
  );

  const handleSearch = async () => {
    if (!imageFile) {
      toast.error('Выберите изображение');
      return;
    }

    const formData = new FormData();
    formData.append('image', imageFile);
    await searchMutation.mutateAsync(formData);
  };

  const handleClear = () => {
    setImageFile(null);
    setImagePreview(null);
    setSearchResults(null);
    setSelectedColor(null);
  };

  // Получаем уникальные категории
  const categories = [...new Set(Object.values(COLOR_PALETTE).map(c => c.category))];

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Поиск по изображению</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
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
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-sm text-gray-500">
                      {selectedColor 
                        ? `Выбран: ${COLOR_PALETTE[selectedColor]?.name}` 
                        : 'Цвет не выбран'}
                    </span>
                    {selectedColor && (
                      <button
                        onClick={() => setSelectedColor(null)}
                        className="text-xs text-red-500 hover:text-red-600"
                      >
                        Сбросить
                      </button>
                    )}
                  </div>
                  
                  <div className="max-h-80 overflow-y-auto pr-2">
                    {categories.map(category => (
                      <ColorGroup
                        key={category}
                        title={category}
                        selectedColor={selectedColor}
                        onColorSelect={setSelectedColor}
                      />
                    ))}
                  </div>
                  
                  <p className="text-xs text-gray-400 mt-3 pt-2 border-t">
                    Выберите цвет для фильтрации результатов поиска
                  </p>
                </div>
              )}
            </div>
            
            <button
              onClick={handleSearch}
              disabled={!imageFile || searchMutation.isLoading}
              className="btn-primary w-full inline-flex items-center justify-center"
            >
              {searchMutation.isLoading ? (
                <Loader size="small" />
              ) : (
                <>
                  <FiSearch className="mr-2" />
                  Найти похожие
                </>
              )}
            </button>
          </div>
        </div>
        
        <div>
          {searchResults && (
            <SimilarImages
              similarImages={searchResults}
              title={`Результаты поиска${selectedColor ? ` (цвет: ${COLOR_PALETTE[selectedColor]?.name})` : ''}`}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchByImage;