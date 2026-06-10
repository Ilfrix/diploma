import io
from unittest.mock import patch

from PIL import Image

from app.models import ImageModel, ProcessStatus, Sample


class TestUploadsRouter:
    
    def test_get_sample_image_redirect(self, client, auth_headers, db_session, test_user, mock_minio):
        """Получение изображения семпла (редирект на временную ссылку)"""

        with patch('app.routers.uploads.minio_client', mock_minio):
            image = ImageModel(
                image_path="samples/user123/sample456.jpg",
                image_hash="hash123",
                mime_type="image/jpeg"
            )
            db_session.add(image)
            db_session.flush()
            
            sample = Sample(
                user_id=test_user.id,
                name="Test Sample",
                image_id=image.id,
                status=ProcessStatus.PROCESSED
            )
            db_session.add(sample)
            db_session.commit()
            
            response = client.get(
                f"/api/uploads/sample/{sample.id}/image",
                headers=auth_headers,
                follow_redirects=False
            )
            
            print(f"Response status: {response.status_code}")
            
            # Проверяем вызовы
            mock_minio.file_exists.assert_called()
            
            assert response.status_code == 307
            assert "Location" in response.headers
    
    def test_get_sample_thumbnail(self, client, auth_headers, db_session, test_user, mock_minio):
        """Получение миниатюры изображения"""
        
        with patch('app.routers.uploads.minio_client', mock_minio):
            # Создаем тестовое изображение
            img = Image.new('RGB', (800, 600), color='blue')
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_bytes = img_byte_arr.getvalue()
            
            image = ImageModel(
                image_path="samples/user123/sample456.jpg",
                image_hash="hash123",
                mime_type="image/jpeg"
            )
            db_session.add(image)
            db_session.flush()
            
            sample = Sample(
                user_id=test_user.id,
                name="Test Sample",
                image_id=image.id,
                status=ProcessStatus.PROCESSED
            )
            db_session.add(sample)
            db_session.commit()
            
            # Настраиваем мок MinIO
            mock_minio.file_exists.return_value = True
            mock_minio.download_file.return_value = img_bytes
            
            response = client.get(
                f"/api/uploads/sample/{sample.id}/image?thumbnail=true&size=200",
                headers=auth_headers
            )
            
            # Проверяем, что методы были вызваны
            mock_minio.file_exists.assert_called_with(image.image_path)
            mock_minio.download_file.assert_called_with(image.image_path)
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert "Cache-Control" in response.headers
    
    def test_get_presigned_url(self, client, auth_headers, db_session, test_user, mock_minio):
        """Получение подписанной URL"""
        
        image = ImageModel(
            image_path="samples/user123/sample456.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Test Sample",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        with patch('app.routers.uploads.minio_client', mock_minio):
            mock_minio['url'].return_value = "https://minio.example.com/presigned/test.jpg"
            
            response = client.get(
                f"/api/uploads/sample/{sample.id}/presigned-url?expires=7200",
                headers=auth_headers
            )
            print('response')
            
            assert response.status_code == 200
            data = response.json()
            assert data["sample_id"] == sample.id
            assert "image_url" in data
            assert data["expires_in"] == 7200
    
    def test_download_sample_image(self, client, auth_headers, db_session, test_user, mock_minio):
        """Скачивание изображения"""
        
        img = Image.new('RGB', (100, 100), color='green')
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        image = ImageModel(
            image_path="samples/user123/sample456.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Test Sample",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        with patch('app.routers.uploads.minio_client', mock_minio):
            mock_minio['download'].return_value = img_bytes
            
            response = client.get(
                f"/api/uploads/sample/{sample.id}/download",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert "attachment" in response.headers["content-disposition"]
    
    def test_get_image_info(self, client, auth_headers, db_session, test_user, mock_minio):
        """Получение информации по изображению."""
        
        image = ImageModel(
            image_path="samples/user123/sample456.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Test Sample",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        with patch('app.routers.uploads.minio_client', mock_minio):
            mock_minio['exists'].return_value = True
            mock_minio['get_file_info'].return_value = {
                "size": 102400,
                "last_modified": "2024-01-01T00:00:00Z",
                "content_type": "image/jpeg",
                "etag": "abc123"
            }
            
            response = client.get(
                f"/api/uploads/sample/{sample.id}/info",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["sample_id"] == sample.id
            assert data["size_bytes"] == 102400
            assert data["size_kb"] == 100.0
    
    def test_check_image_exists(self, client, auth_headers, db_session, test_user, mock_minio):
        """Проверка существования изображения"""
        
        image = ImageModel(
            image_path="samples/user123/sample456.jpg",
            image_hash="hash123",
            mime_type="image/jpeg"
        )
        db_session.add(image)
        db_session.flush()
        
        sample = Sample(
            user_id=test_user.id,
            name="Test Sample",
            image_id=image.id,
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        response = client.get(
            f"/api/uploads/check/{sample.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
    
    def test_check_image_not_exists(self, client, auth_headers):
        """Проверка несуществующего изображения"""
        response = client.get(
            "/api/uploads/check/nonexistent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
    
    def test_batch_presigned_urls(self, client, auth_headers, db_session, test_user, mock_minio):
        """Batch получение подписанных URL"""
        
        samples = []
        for i in range(3):
            image = ImageModel(
                image_path=f"samples/user123/sample{i}.jpg",
                image_hash=f"hash{i}",
                mime_type="image/jpeg"
            )
            db_session.add(image)
            db_session.flush()
            
            sample = Sample(
                user_id=test_user.id,
                name=f"Sample {i}",
                image_id=image.id,
                status=ProcessStatus.PROCESSED
            )
            db_session.add(sample)
            samples.append(sample)
        
        db_session.commit()
        with patch('app.routers.uploads.minio_client', mock_minio):
            sample_ids = ",".join([s.id for s in samples])
            response = client.get(
                f"/api/uploads/batch/presigned-urls?sample_ids={sample_ids}",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["urls"]) == 3
            assert all(url["exists"] for url in data["urls"])
