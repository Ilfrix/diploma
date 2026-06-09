import React, { useContext, useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthContext } from '../../contexts/AuthContext';
import { FiLogOut, FiHome, FiSearch, FiPlus, FiUser, FiChevronDown } from 'react-icons/fi';

const Navbar = () => {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!user) return null;

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-content">
          {/* Логотип - слева */}
          <Link to="/samples" className="navbar-logo">
            FlexSearch
          </Link>
          
          {/* Центральные кнопки навигации */}
          <div className="navbar-nav">
            <Link to="/samples" className="btn-nav">
              <FiHome size={18} />
              <span>Мои эталоны</span>
            </Link>
            
            <Link to="/search" className="btn-nav">
              <FiSearch size={18} />
              <span>Поиск</span>
            </Link>
            
            <Link to="/samples/create" className="btn-nav-primary">
              <FiPlus size={18} />
              <span>Создать</span>
            </Link>
          </div>
          
          {/* Профиль пользователя - справа */}
          <div className="navbar-profile" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="profile-button"
            >
              <div className="profile-avatar">
                <FiUser className="profile-avatar-icon" size={18} />
              </div>
              <span className="profile-username">{user.username}</span>
              <FiChevronDown 
                size={16} 
                className={`profile-chevron ${isDropdownOpen ? 'rotate-180' : ''}`}
              />
            </button>
            
            {/* Выпадающее меню */}
            {isDropdownOpen && (
              <div className="dropdown-menu">
                <div className="dropdown-header">
                  <p className="dropdown-label">Вход выполнен как</p>
                  <p className="dropdown-username">{user.username}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="dropdown-logout"
                >
                  <FiLogOut size={16} />
                  Выйти из аккаунта
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;