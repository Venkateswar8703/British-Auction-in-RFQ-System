import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, DEMO_CREDENTIALS } from '../context/AuthContext';
import { Lock, Mail, AlertCircle, Zap } from 'lucide-react';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState<string>('buyer@meridian.com');
  const [password, setPassword] = useState<string>('MeridianBuyer2026!');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please verify credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoSelect = async (demoKey: keyof typeof DEMO_CREDENTIALS) => {
    const creds = DEMO_CREDENTIALS[demoKey];
    setEmail(creds.email);
    setPassword(creds.password);
    setIsLoading(true);
    setError(null);
    try {
      await login(creds.email, creds.password);
      if (demoKey.startsWith('buyer')) {
        navigate('/');
      } else {
        navigate('/portal');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-meridian-bg text-meridian-ink">
      <div className="w-full max-w-md bg-meridian-surface border border-meridian-line p-8 space-y-8">
        
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-10 h-10 bg-meridian-lime border border-meridian-ink flex items-center justify-center font-mono font-bold text-meridian-ink text-xl mx-auto mb-3">
            M
          </div>
          <h1 className="font-heading text-2xl font-medium tracking-wider text-meridian-ink uppercase">
            MERIDIAN
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.08em] text-meridian-muted">
            British Auction Logistics Terminal
          </p>
        </div>

        {/* One-Click Demo Personas */}
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-meridian-muted uppercase tracking-wider">
            <Zap className="w-3.5 h-3.5 text-meridian-ink" />
            <span>Fast Demo Sign-In (One-Click)</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <button
              type="button"
              onClick={() => handleDemoSelect('buyer')}
              className="p-2.5 text-left border border-meridian-line bg-meridian-surface hover:bg-meridian-surfaceDeep transition-colors"
            >
              <div className="font-bold text-meridian-ink">Buyer (Admin)</div>
              <div className="text-[10px] text-meridian-muted">Meridian VP Global</div>
            </button>

            <button
              type="button"
              onClick={() => handleDemoSelect('maersk')}
              className="p-2.5 text-left border border-meridian-line bg-meridian-surface hover:bg-meridian-surfaceDeep transition-colors"
            >
              <div className="font-bold text-meridian-ink">Maersk Line</div>
              <div className="text-[10px] text-meridian-muted">Supplier Carrier</div>
            </button>

            <button
              type="button"
              onClick={() => handleDemoSelect('hapag')}
              className="p-2.5 text-left border border-meridian-line bg-meridian-surface hover:bg-meridian-surfaceDeep transition-colors"
            >
              <div className="font-bold text-meridian-ink">Hapag-Lloyd</div>
              <div className="text-[10px] text-meridian-muted">Supplier Carrier</div>
            </button>

            <button
              type="button"
              onClick={() => handleDemoSelect('msc')}
              className="p-2.5 text-left border border-meridian-line bg-meridian-surface hover:bg-meridian-surfaceDeep transition-colors"
            >
              <div className="font-bold text-meridian-ink">MSC Shipping</div>
              <div className="text-[10px] text-meridian-muted">Supplier Carrier</div>
            </button>
          </div>
        </div>

        <div className="relative flex py-1 items-center">
          <div className="flex-grow border-t border-meridian-line"></div>
          <span className="flex-shrink mx-3 text-[10px] font-mono uppercase text-meridian-muted tracking-widest">
            or manual login
          </span>
          <div className="flex-grow border-t border-meridian-line"></div>
        </div>

        {error && (
          <div className="p-3 bg-meridian-orange text-meridian-ink border border-meridian-ink text-xs font-mono flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4 font-mono text-xs">
          <div>
            <label htmlFor="login-email" className="text-[11px] uppercase tracking-[0.08em] text-meridian-muted block mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-meridian-muted absolute left-3 top-2.5" />
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-meridian-surface border border-meridian-line pl-9 pr-3 py-2 text-meridian-ink focus:border-meridian-ink focus-visible:ring-2 focus-visible:ring-meridian-ink outline-none"
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="login-password" className="text-[11px] uppercase tracking-[0.08em] text-meridian-muted block mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-meridian-muted absolute left-3 top-2.5" />
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-meridian-surface border border-meridian-line pl-9 pr-3 py-2 text-meridian-ink focus:border-meridian-ink focus-visible:ring-2 focus-visible:ring-meridian-ink outline-none"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary w-full py-3 font-mono font-bold uppercase tracking-wider text-xs focus-visible:ring-2 focus-visible:ring-meridian-ink outline-none"
          >
            {isLoading ? 'Verifying Credentials...' : 'Authenticate'}
          </button>
        </form>

        <div className="pt-2 text-center text-[10px] font-mono text-meridian-muted">
          MERIDIAN British Auction Exchange • v1.0.0
        </div>
      </div>
    </div>
  );
};
