import pytest
from unittest.mock import patch, AsyncMock
from fastapi import UploadFile
import io
from app.models import Sample, ProcessStatus, ImageModel


class TestSamplesRouter:
    
    def test_create_sample_success(self, client, auth_headers, test_image_bytes, mock_minio):
        """Успешное создание семпла"""
        with patch('app.routers.samples.minio_client', mock_minio):
            files = {
                "image": ("test.jpg", test_image_bytes, "image/jpeg")
            }
            data = {
                "name": "Test Sample",
                "description": "Test Description"
            }

            response = client.post(
                "/api/samples",
                headers=auth_headers,
                files=files,
                data=data
            )

            if response.status_code == 500:
                print(f"Response content: {response.content}")
                print(f"Response text: {response.text}")

            assert response.status_code == 202
    
    def test_create_sample_invalid_file_type(self, client, auth_headers):
        """Создание семпла с не-изображением"""
        files = {
            "image": ("test.txt", b"not an image", "text/plain")
        }
        data = {"name": "Test Sample"}
        
        response = client.post(
            "/api/samples",
            headers=auth_headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 400
        assert "must be an image" in response.json()["detail"].lower()
    
    def test_create_sample_duplicate(self, client, auth_headers, test_image_bytes, mock_minio, db_session, test_user, mock_kafka):
        """Создание дубликата изображения"""
        # Сначала создаем семпл
        with patch('app.routers.samples.minio_client', mock_minio):
            files = {
                "image": ("test.jpg", test_image_bytes, "image/jpeg")
            }
            data = {"name": "First Sample"}

            response1 = client.post(
                "/api/samples",
                headers=auth_headers,
                files=files,
                data=data
            )
            assert response1.status_code == 202
            
            # Пытаемся создать дубликат
            response2 = client.post(
                "/api/samples",
                headers=auth_headers,
                files=files,
                data={"name": "Duplicate Sample"}
            )
            
            assert response2.status_code == 409
            assert "duplicate" in response2.json()["detail"].lower()
    
    def test_get_sample(self, client, auth_headers, db_session, test_user):
        """Получение информации о семпле"""
        # Создаем тестовый семпл
        sample = Sample(
            user_id=test_user.id,
            name="Test Sample",
            description="Test Desc",
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        response = client.get(
            f"/api/samples/{sample.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample.id
        assert data["name"] == "Test Sample"
    
    def test_get_sample_not_found(self, client, auth_headers):
        """Получение несуществующего семпла"""
        response = client.get(
            "/api/samples/nonexistent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_get_sample_other_user(self, client, auth_headers, db_session, test_user2):
        """Доступ к семплу другого пользователя"""
        sample = Sample(
            user_id=test_user2.id,
            name="Other User Sample",
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        response = client.get(
            f"/api/samples/{sample.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_list_samples(self, client, auth_headers, db_session, test_user):
        """Получение списка семплов"""
        # Создаем несколько семплов
        for i in range(3):
            sample = Sample(
                user_id=test_user.id,
                name=f"Sample {i}",
                status=ProcessStatus.PROCESSED
            )
            db_session.add(sample)
        db_session.commit()
        
        response = client.get(
            "/api/samples",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
        assert all("name" in item for item in data)
    
    def test_list_samples_with_filter(self, client, auth_headers, db_session, test_user):
        """Список семплов с фильтром по статусу"""
        sample1 = Sample(
            user_id=test_user.id,
            name="Pending Sample",
            status=ProcessStatus.PENDING
        )
        sample2 = Sample(
            user_id=test_user.id,
            name="PROCESSED Sample",
            status=ProcessStatus.PROCESSED
        )
        db_session.add_all([sample1, sample2])
        db_session.commit()
        
        response = client.get(
            "/api/samples?status_filter=pending",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "pending" for item in data)
    
    def test_update_sample(self, client, auth_headers, db_session, test_user):
        """Обновление семпла"""
        sample = Sample(
            user_id=test_user.id,
            name="Original Name",
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        response = client.put(
            f"/api/samples/{sample.id}",
            headers=auth_headers,
            json={"name": "Updated Name", "description": "New Description"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New Description"
    
    def test_delete_sample(self, client, auth_headers, db_session, test_user, mock_minio):
        """Удаление семпла"""
        sample = Sample(
            user_id=test_user.id,
            name="To Delete",
            status=ProcessStatus.PROCESSED
        )
        db_session.add(sample)
        db_session.commit()
        
        response = client.delete(
            f"/api/samples/{sample.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Sample deleted successfully"
        
        # Проверяем, что семпл удален из БД
        deleted_sample = db_session.query(Sample).filter(Sample.id == sample.id).first()
        assert deleted_sample is None
    
    def test_get_sample_stats(self, client, auth_headers, db_session, test_user):
        """Получение статистики по семплам"""
        # Создаем семплы с разными статусами
        samples = [
            Sample(user_id=test_user.id, name="Sample 1", status=ProcessStatus.PROCESSED),
            Sample(user_id=test_user.id, name="Sample 2", status=ProcessStatus.PENDING),
            Sample(user_id=test_user.id, name="Sample 3", status=ProcessStatus.PROCESSED),
            Sample(user_id=test_user.id, name="Sample 4", status=ProcessStatus.FAILED),
        ]
        db_session.add_all(samples)
        db_session.commit()
        
        response = client.get(
            "/api/samples/stats/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_samples"] == 4
