import pytest
from unittest.mock import patch
from app.models import User


class TestAuthRouter:
    
    def test_register_success(self, client, db_session):
        """Успешная регистрация нового пользователя"""
        response = client.post(
            "/api/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # Проверяем, что пользователь создан в БД
        user = db_session.query(User).filter(User.username == "newuser").first()
        assert user is not None
        assert user.email == "newuser@example.com"
    
    def test_register_duplicate_username(self, client, test_user):
        """Регистрация с уже существующим username"""
        response = client.post(
            "/api/register",
            json={
                "username": test_user.username,
                "email": "different@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_duplicate_email(self, client, test_user):
        """Регистрация с уже существующим email"""
        response = client.post(
            "/api/register",
            json={
                "username": "differentuser",
                "email": test_user.email,
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_missing_fields(self, client):
        """Регистрация без обязательных полей"""
        response = client.post(
            "/api/register",
            json={"username": "onlyusername"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_login_success(self, client, test_user):
        """Успешный вход"""
        # Сначала создаем пользователя с реальным паролем (не через хэш)
        from app.auth import hash_password
        test_user.password_hash = hash_password("testpassword123")
        client.app.dependency_overrides  # Обновляем
        
        response = client.post(
            "/api/login",
            json={
                "username": test_user.username,
                "password": "testpassword123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client, test_user):
        """Вход с неверным паролем"""
        response = client.post(
            "/api/login",
            json={
                "username": test_user.username,
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    def test_login_nonexistent_user(self, client):
        """Вход с несуществующим пользователем"""
        response = client.post(
            "/api/login",
            json={
                "username": "nonexistent",
                "password": "somepassword"
            }
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    def test_login_disabled_user(self, client, db_session, test_user):
        """Вход с отключенным пользователем"""
        test_user.is_active = False
        db_session.commit()
        
        from app.auth import hash_password
        test_user.password_hash = hash_password("testpassword123")
        db_session.commit()
        
        response = client.post(
            "/api/login",
            json={
                "username": test_user.username,
                "password": "testpassword123"
            }
        )
        
        assert response.status_code == 401
