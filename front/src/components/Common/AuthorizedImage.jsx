import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../contexts/AuthContext';

const AuthorizedImage = ({
  sampleId,
  alt,
  className,
  size = 200,
  thumbnail = true
}) => {
  const [imageUrl, setImageUrl] = useState(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const { token } = useContext(AuthContext);

  useEffect(() => {
    if (!sampleId || !token) {
      setLoading(false);
      return;
    }

    const fetchImage = async () => {
      setLoading(true);
      try {
        // Формирование URL в зависимости от типа
        let url;
        if (thumbnail) {
          url = `http://localhost:8000/api/uploads/thumbnail/${sampleId}?size=${size}`;
        } else {
          url = `http://localhost:8000/api/uploads/sample/${sampleId}/image`;
        }

        const response = await fetch(url, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const blob = await response.blob();
          const objectUrl = URL.createObjectURL(blob);
          setImageUrl(objectUrl);
          setError(false);
        } else {
          console.error('Failed to load image:', response.status);
          setError(true);
        }
      } catch (err) {
        console.error('Error loading image:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchImage();

    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [sampleId, token, size, thumbnail]);

  if (loading) {
    return <div className={`${className} bg-gray-200 animate-pulse`} />;
  }

  if (error || !imageUrl) {
    return (
      <img
        src="/placeholder.jpg"
        alt={alt}
        className={className}
      />
    );
  }

  return (
    <img
      src={imageUrl}
      alt={alt}
      className={className}
    />
  );
};

export default AuthorizedImage;
