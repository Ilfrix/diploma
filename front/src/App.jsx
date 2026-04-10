import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/Layout/PrivateRoute';
import Navbar from './components/Layout/Navbar';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import SampleList from './components/Samples/SampleList';
import SampleDetail from './components/Samples/SampleDetail';
import SampleForm from './components/Samples/SampleForm';
import SearchByImage from './components/Search/SearchByImage';

function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="min-h-screen bg-gray-50">
          <Navbar />
          <main className="container mx-auto px-4 py-8">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/" element={<Navigate to="/samples" />} />
              <Route path="/samples" element={
                <PrivateRoute>
                  <SampleList />
                </PrivateRoute>
              } />
              <Route path="/samples/create" element={
                <PrivateRoute>
                  <SampleForm />
                </PrivateRoute>
              } />
              <Route path="/samples/:id" element={
                <PrivateRoute>
                  <SampleDetail />
                </PrivateRoute>
              } />
              <Route path="/samples/:id/edit" element={
                <PrivateRoute>
                  <SampleForm />
                </PrivateRoute>
              } />
              <Route path="/search" element={
                <PrivateRoute>
                  <SearchByImage />
                </PrivateRoute>
              } />
            </Routes>
          </main>
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;