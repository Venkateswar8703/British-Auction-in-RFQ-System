import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { AppShell } from './components/layout/AppShell';

import { Login } from './pages/Login';
import { CommandCenter } from './pages/CommandCenter';
import { AuctionListing } from './pages/AuctionListing';
import { LiveAuctionRoom } from './pages/LiveAuctionRoom';
import { CreateEditRfq } from './pages/CreateEditRfq';
import { AuctionDetails } from './pages/AuctionDetails';
import { SupplierPortal } from './pages/SupplierPortal';

const HomeRedirect: React.FC = () => {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return user.role === 'buyer' ? <CommandCenter /> : <SupplierPortal />;
};

const ProtectedRoute: React.FC<{ children: React.ReactNode; buyerOnly?: boolean }> = ({
  children,
  buyerOnly = false,
}) => {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (buyerOnly && user.role !== 'buyer') {
    return <Navigate to="/portal" replace />;
  }
  return <AppShell>{children}</AppShell>;
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <WebSocketProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <HomeRedirect />
                </ProtectedRoute>
              }
            />

            <Route
              path="/auctions"
              element={
                <ProtectedRoute>
                  <AuctionListing />
                </ProtectedRoute>
              }
            />

            <Route
              path="/auctions/:rfqId"
              element={
                <ProtectedRoute>
                  <AuctionDetails />
                </ProtectedRoute>
              }
            />

            <Route
              path="/live/:rfqId"
              element={
                <ProtectedRoute>
                  <LiveAuctionRoom />
                </ProtectedRoute>
              }
            />

            <Route
              path="/create-rfq"
              element={
                <ProtectedRoute buyerOnly>
                  <CreateEditRfq />
                </ProtectedRoute>
              }
            />

            <Route
              path="/edit-rfq/:rfqId"
              element={
                <ProtectedRoute buyerOnly>
                  <CreateEditRfq />
                </ProtectedRoute>
              }
            />

            <Route
              path="/portal"
              element={
                <ProtectedRoute>
                  <SupplierPortal />
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </WebSocketProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;

