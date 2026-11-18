import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password?: string) => Promise<void>;
  logout: () => void;
  switchDemoUser: (role: 'buyer' | 'maersk' | 'hapag' | 'msc') => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const DEMO_CREDENTIALS = {
  buyer: { email: 'buyer@meridian.com', password: 'MeridianBuyer2026!', label: 'Eleanor Vance (Buyer VP)' },
  buyer2: { email: 'alex.chen@meridian.com', password: 'MeridianBuyer2026!', label: 'Alex Chen (Senior Buyer)' },
  maersk: { email: 'bids@maersk.com', password: 'SupplierPass2026!', label: 'Maersk Logistics (Supplier)' },
  hapag: { email: 'quotes@hapag-lloyd.com', password: 'SupplierPass2026!', label: 'Hapag-Lloyd (Supplier)' },
  msc: { email: 'rfq@msc.com', password: 'SupplierPass2026!', label: 'MSC Mediterranean (Supplier)' },
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('meridian_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      const storedToken = localStorage.getItem('meridian_token');
      if (storedToken) {
        try {
          const currentUser = await api.getMe();
          setUser(currentUser);
        } catch {
          localStorage.removeItem('meridian_token');
          setToken(null);
          setUser(null);
        }
      }
      setIsLoading(false);
    }
    loadUser();
  }, []);

  const login = async (email: string, password = 'MeridianBuyer2026!') => {
    setIsLoading(true);
    try {
      const res = await api.login(email, password);
      localStorage.setItem('meridian_token', res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('meridian_token');
    setToken(null);
    setUser(null);
  };

  const switchDemoUser = async (target: 'buyer' | 'maersk' | 'hapag' | 'msc') => {
    const creds = DEMO_CREDENTIALS[target];
    if (creds) {
      await login(creds.email, creds.password);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, switchDemoUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

