import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { samplesService } from '../../services/samples';
import { useDropzone } from 'react-dropzone';
import SimilarImages from './SimilarImages';
import Loader from '../Common/Loader';
import { FiUpload, FiSearch } from 'react-icons/fi';
import toast from 'react-hot-toast';

const SearchByImage = () => {
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [limit, setLimit] = useState(10);
  const [threshold, setThreshold] = useState(0.7);

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
    (formData) => samplesService.searchByImage(formData, limit, threshold),
    {
      onSuccess: (data) => {
        setSearchResults(data);
        if (data.length === 0) {
          toast('Похожих изображений не найдено', { icon: '🔍' });
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
  };

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
              <label className="block text-gray-700 mb-2">Максимум результатов: {limit}</label>
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
              <label className="block text-gray-700 mb-2">Порог схожести: {threshold}</label>
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
              title="Результаты поиска"
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchByImage;