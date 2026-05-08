// src/components/Search/SimilarImages.jsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { samplesService } from '../../services/samples';
import { Link } from 'react-router-dom';
import Loader from '../Common/Loader';
import AuthorizedImage from '../Common/AuthorizedImage';

const SimilarImages = ({ sampleId, sampleName, similarImages: externalImages, title }) => {
  // Все хуки должны вызываться в одном порядке всегда
  const { data: similarData, isLoading } = useQuery(
    ['similar', sampleId],
    () => samplesService.getSimilar(sampleId, 12, 0.6),
    { enabled: !!sampleId && !externalImages } // Запрос только если есть sampleId и нет externalImages
  );

  // Режим 1: Поиск по загруженному изображению (есть externalImages)
  if (externalImages) {
    if (externalImages.length === 0) {
      return (
        <div className="text-center py-8">
          <p className="text-gray-500">Похожих изображений не найдено</p>
        </div>
      );
    }

    return (
      <div>
        <h2 className="text-2xl font-bold mb-4">
          {title || "Результаты поиска"}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {externalImages.map((image, index) => (
            <Link
              key={image.sample_id || index}
              to={`/samples/${image.sample_id}`}
              className="card group"
            >
              <div className="relative">
                <AuthorizedImage
                  sampleId={image.sample_id}
                  alt={image.name}
                  className="w-full h-48 object-cover"
                  thumbnail={false}
                />
                <div className="absolute top-2 right-2 bg-blue-600 text-white px-2 py-1 rounded-full text-sm">
                  {Math.round(image.similarity_score * 100)}%
                </div>
              </div>
              <div className="p-3">
                <h3 className="font-semibold truncate">{image.name}</h3>
                {image.description && (
                  <p className="text-gray-600 text-sm truncate">{image.description}</p>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  // Режим 2: Поиск по ID образца (есть sampleId)
  // Если запрос еще загружается
  if (isLoading) {
    return <Loader />;
  }

  const images = similarData?.similar_images || [];
  const queryName = sampleName || similarData?.query_name;

  if (images.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500">Похожих изображений не найдено</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">
        {title || `Похожие на "${queryName}"`}
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {images.map((image, index) => (
          <Link
            key={image.sample_id || index}
            to={`/samples/${image.sample_id}`}
            className="card group"
          >
            <div className="relative">
              <AuthorizedImage
                sampleId={image.sample_id}
                alt={image.name}
                className="w-full h-48 object-cover"
                size={400}
                thumbnail={false}
              />
              <div className="absolute top-2 right-2 bg-blue-600 text-white px-2 py-1 rounded-full text-sm">
                {Math.round(image.similarity_score * 100)}%
              </div>
            </div>
            <div className="p-3">
              <h3 className="font-semibold truncate">{image.name}</h3>
              {image.description && (
                <p className="text-gray-600 text-sm truncate">{image.description}</p>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default SimilarImages;