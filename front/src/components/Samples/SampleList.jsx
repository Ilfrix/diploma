import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { samplesService } from '../../services/samples';
import SampleCard from './SampleCard';
import Loader from '../Common/Loader';
import { FiPlus, FiSearch } from 'react-icons/fi';

const SampleList = () => {
  const [page, setPage] = useState(0);
  const limit = 12;

  const { data: samples, isLoading, error } = useQuery(
    ['samples', page],
    () => samplesService.getAll({ skip: page * limit, limit }),
    {
      keepPreviousData: true,
    }
  );

  if (isLoading) return <Loader />;
  if (error) return <div className="text-center text-red-600">Ошибка загрузки</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Мои эталоны</h1>
        <div className="space-x-3">
          <Link to="/search" className="btn-secondary inline-flex items-center">
            <FiSearch className="mr-2" />
            Поиск по изображению
          </Link>
          <Link to="/samples/create" className="btn-primary inline-flex items-center">
            <FiPlus className="mr-2" />
            Создать эталон
          </Link>
        </div>
      </div>

      {samples && samples.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">У вас пока нет эталонов</p>
          <Link to="/samples/create" className="btn-primary inline-block mt-4">
            Создать первый эталон
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {samples?.map((sample) => (
              <SampleCard key={sample.id} sample={sample} />
            ))}
          </div>

          <div className="flex justify-center mt-8 space-x-4">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="btn-secondary disabled:opacity-50"
            >
              Предыдущая
            </button>
            <span className="py-2">Страница {page + 1}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={samples?.length < limit}
              className="btn-secondary disabled:opacity-50"
            >
              Следующая
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default SampleList;
