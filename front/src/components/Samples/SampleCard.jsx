// src/components/Samples/SampleCard.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import { FiEye, FiEdit2, FiTrash2 } from 'react-icons/fi';
import AuthorizedImage from '../Common/AuthorizedImage';

const SampleCard = ({ sample, onDelete }) => {
  return (
    <div className="card group">
      <div className="relative h-48 overflow-hidden bg-gray-200 flex items-center justify-center">
        <AuthorizedImage
          sampleId={sample.id}
          alt={sample.name}
          className="max-w-full max-h-full object-contain"
          size={200}
          thumbnail={true}
        />
        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all duration-300 flex items-center justify-center opacity-0 group-hover:opacity-100">
          <Link
            to={`/samples/${sample.id}`}
            className="bg-white text-gray-800 p-2 rounded-full mx-1 hover:bg-blue-600 hover:text-white transition-colors"
          >
            <FiEye size={20} />
          </Link>
          <Link
            to={`/samples/${sample.id}/edit`}
            className="bg-white text-gray-800 p-2 rounded-full mx-1 hover:bg-green-600 hover:text-white transition-colors"
          >
            <FiEdit2 size={20} />
          </Link>
          {onDelete && (
            <button
              onClick={() => onDelete(sample.id)}
              className="bg-white text-gray-800 p-2 rounded-full mx-1 hover:bg-red-600 hover:text-white transition-colors"
            >
              <FiTrash2 size={20} />
            </button>
          )}
        </div>
      </div>
      
      <div className="p-4">
        <h3 className="font-semibold text-lg mb-1 truncate">{sample.name}</h3>
        {sample.description && (
          <p className="text-gray-600 text-sm mb-2 line-clamp-2">{sample.description}</p>
        )}
        <p className="text-gray-400 text-xs">
          {formatDistanceToNow(new Date(sample.created_at), { addSuffix: true, locale: ru })}
        </p>
      </div>
    </div>
  );
};

export default SampleCard;