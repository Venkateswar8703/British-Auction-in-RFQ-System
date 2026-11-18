import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { 
  Radio, 
  Layers, 
  PlusCircle, 
  LayoutDashboard, 
  Briefcase, 
  LogOut, 
  ChevronDown,
  Bell,
  Clock,
  Award,
  Check
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, logout, switchDemoUser } = useAuth();
  const location = useLocation();
  const [showDemoMenu, setShowDemoMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [hasActiveAuctions, setHasActiveAuctions] = useState(false);

  // In-app Notification Center (Improvement #5)
  const [notifications, setNotifications] = useState([
    {
      id: '1',
      title: 'Auction Window Extended (+5m)',
      message: 'RFQ-2026-LIVE-DEMO received a qualifying quote inside trigger window.',
      time: 'Just now',
      type: 'extension',
      unread: true,
      link: '/live/demo',
    },
    {
      id: '2',
      title: 'L1 Leadership Swapped',
      message: 'New lowest quote placed on Shanghai → Melbourne corridor ($2,150.00).',
      time: '2m ago',
      type: 'bid',
      unread: true,
      link: '/live/demo',
    },
    {
      id: '3',
      title: 'Official Award Notice',
      message: 'RFQ-2026-MEL-SYD has been awarded to Hapag-Lloyd ($2,140.00).',
      time: '14m ago',
      type: 'award',
      unread: false,
      link: '/auctions',
    },
  ]);

  const unreadCount = notifications.filter((n) => n.unread).length;

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));
  };

  const isBuyer = user?.role === 'buyer';

  // Check if there are active auctions the user can participate in
  useEffect(() => {
    let isMounted = true;
    const checkActive = async () => {
      try {
        const activeList = await api.listRfqs({ status: 'ACTIVE' });
        if (isMounted) {
          setHasActiveAuctions(activeList.length > 0);
        }
      } catch {
        // ignore
      }
    };
    checkActive();
    const interval = setInterval(checkActive, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [user]);

  return (
    <header className="h-12 bg-meridian-instrument text-meridian-ivory border-b border-black/40 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        
        {/* Left: Brand & Wordmark */}
        <div className="flex items-center gap-5">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-6 h-6 bg-meridian-lime flex items-center justify-center font-mono font-bold text-meridian-graphite text-xs tracking-tighter">
              M
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-heading font-semibold text-sm text-meridian-ivory tracking-wider uppercase">
                MERIDIAN
              </span>
              <span className="text-[9px] font-mono uppercase bg-white/10 px-1 py-0.2 text-meridian-muted tracking-widest hidden sm:inline">
                EXCHANGE
              </span>
            </div>
          </Link>

          {/* Navigation links */}
          <nav className="hidden md:flex items-center gap-1 border-l border-white/15 pl-4 ml-1">
            {isBuyer ? (
              <>
                <Link
                  to="/"
                  className={`px-2.5 py-1 text-xs font-mono uppercase tracking-wider transition-colors flex items-center gap-1.5 ${
                    location.pathname === '/' 
                      ? 'bg-white/15 text-meridian-lime' 
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  <LayoutDashboard className="w-3.5 h-3.5" />
                  Command Center
                </Link>
                <Link
                  to="/auctions"
                  className={`px-2.5 py-1 text-xs font-mono uppercase tracking-wider transition-colors flex items-center gap-1.5 ${
                    location.pathname === '/auctions' 
                      ? 'bg-white/15 text-meridian-lime' 
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  Auctions
                </Link>
                <Link
                  to="/create-rfq"
                  className={`px-2.5 py-1 text-xs font-mono uppercase tracking-wider transition-colors flex items-center gap-1.5 ${
                    location.pathname === '/create-rfq' 
                      ? 'bg-white/15 text-meridian-lime' 
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  Create RFQ
                </Link>
              </>
            ) : (
              <>
                <Link
                  to="/portal"
                  className={`px-2.5 py-1 text-xs font-mono uppercase tracking-wider transition-colors flex items-center gap-1.5 ${
                    location.pathname === '/portal' 
                      ? 'bg-white/15 text-meridian-lime' 
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  <Briefcase className="w-3.5 h-3.5" />
                  Carrier Portal
                </Link>
                <Link
                  to="/auctions"
                  className={`px-2.5 py-1 text-xs font-mono uppercase tracking-wider transition-colors flex items-center gap-1.5 ${
                    location.pathname === '/auctions' 
                      ? 'bg-white/15 text-meridian-lime' 
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  Invited RFQs
                </Link>
              </>
            )}
          </nav>
        </div>

        {/* Center: Signature Live Demo Spotlight */}
        <div className="flex items-center gap-3">
          <Link
            to="/live/demo"
            className="flex items-center gap-1.5 px-2.5 py-1 bg-meridian-lime text-meridian-ink text-xs font-mono font-bold uppercase tracking-wider hover:opacity-95 transition-all border border-meridian-ink"
            title="Open Signature Live British Auction Room"
          >
            {hasActiveAuctions && (
              <span className="w-1.5 h-1.5 rounded-full bg-meridian-ink beacon-pulse" />
            )}
            <Radio className="w-3.5 h-3.5" />
            <span>Live Room</span>
          </Link>
        </div>

        {/* Right: Demo Persona Switcher Group & User Menu */}
        <div className="flex items-center gap-3">
          {/* Persona Switcher in DEMO group with dashed outline */}
          <div className="relative">
            <div className="border border-dashed border-white/40 px-2 py-0.5 flex items-center gap-1.5 font-mono text-[11px] bg-white/5">
              <span className="text-[9px] uppercase tracking-wider text-white/50 font-semibold">DEMO:</span>
              <button
                onClick={() => setShowDemoMenu(!showDemoMenu)}
                className="text-meridian-lime font-bold uppercase hover:underline flex items-center gap-1"
                title="Switch persona for demo evaluation"
              >
                <span>{user?.role === 'buyer' ? 'Buyer VP' : user?.supplier?.code || 'Carrier'}</span>
                <ChevronDown className="w-3 h-3 text-white/60" />
              </button>
            </div>

            {showDemoMenu && (
              <div 
                className="absolute right-0 mt-1 w-64 bg-meridian-instrument text-meridian-ivory border border-white/20 p-1 shadow-float z-50 text-xs font-mono"
                onMouseLeave={() => setShowDemoMenu(false)}
              >
                <div className="px-2 py-1 text-[10px] text-meridian-muted uppercase tracking-widest border-b border-white/10 mb-1">
                  Demo Personas (One-Click)
                </div>
                <button
                  onClick={() => { switchDemoUser('buyer'); setShowDemoMenu(false); }}
                  className={`w-full text-left px-2 py-1.5 hover:bg-white/10 flex items-center justify-between ${
                    user?.role === 'buyer' ? 'text-meridian-lime font-bold' : 'text-meridian-ivory'
                  }`}
                >
                  <span>1. Eleanor Vance (Buyer VP)</span>
                  <span className="text-[10px] text-meridian-muted uppercase">Buyer</span>
                </button>
                <button
                  onClick={() => { switchDemoUser('maersk'); setShowDemoMenu(false); }}
                  className={`w-full text-left px-2 py-1.5 hover:bg-white/10 flex items-center justify-between ${
                    user?.supplier?.code === 'MAERSK' ? 'text-meridian-lime font-bold' : 'text-meridian-ivory'
                  }`}
                >
                  <span>2. Maersk Line</span>
                  <span className="text-[10px] text-meridian-muted uppercase">Supplier</span>
                </button>
                <button
                  onClick={() => { switchDemoUser('hapag'); setShowDemoMenu(false); }}
                  className={`w-full text-left px-2 py-1.5 hover:bg-white/10 flex items-center justify-between ${
                    user?.supplier?.code === 'HAPAG' ? 'text-meridian-lime font-bold' : 'text-meridian-ivory'
                  }`}
                >
                  <span>3. Hapag-Lloyd</span>
                  <span className="text-[10px] text-meridian-muted uppercase">Supplier</span>
                </button>
                <button
                  onClick={() => { switchDemoUser('msc'); setShowDemoMenu(false); }}
                  className={`w-full text-left px-2 py-1.5 hover:bg-white/10 flex items-center justify-between ${
                    user?.supplier?.code === 'MSC' ? 'text-meridian-lime font-bold' : 'text-meridian-ivory'
                  }`}
                >
                  <span>4. MSC Mediterranean</span>
                  <span className="text-[10px] text-meridian-muted uppercase">Supplier</span>
                </button>
              </div>
            )}
          </div>

          {/* Improvement #5: In-app Notification Center Bell */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="p-1.5 text-white/70 hover:text-white relative transition-colors"
              title="Notifications & Alerts"
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full bg-meridian-lime" />
              )}
            </button>

            {showNotifications && (
              <div
                className="absolute right-0 mt-1 w-80 bg-meridian-instrument text-meridian-ivory border border-white/20 shadow-float z-50 text-xs font-mono p-2"
                onMouseLeave={() => setShowNotifications(false)}
              >
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/10 px-1">
                  <div className="text-[10px] text-meridian-muted uppercase tracking-wider font-bold">
                    Activity & Alerts ({unreadCount} unread)
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllRead}
                      className="text-[10px] text-meridian-lime hover:underline flex items-center gap-1"
                    >
                      <Check className="w-3 h-3" />
                      Mark read
                    </button>
                  )}
                </div>

                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {notifications.map((item) => (
                    <Link
                      key={item.id}
                      to={item.link}
                      onClick={() => setShowNotifications(false)}
                      className={`block p-2 rounded transition-colors ${
                        item.unread ? 'bg-white/10 hover:bg-white/15' : 'bg-transparent hover:bg-white/5 opacity-80'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[11px] font-semibold text-meridian-lime mb-0.5">
                        <span className="flex items-center gap-1.5">
                          {item.type === 'award' ? (
                            <Award className="w-3 h-3 text-meridian-lime" />
                          ) : (
                            <Clock className="w-3 h-3 text-meridian-orange" />
                          )}
                          {item.title}
                        </span>
                        <span className="text-[9px] text-meridian-muted">{item.time}</span>
                      </div>
                      <p className="text-[10px] text-white/70 leading-snug">
                        {item.message}
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* User Profile info with tooltip & logout */}
          {user ? (
            <div className="flex items-center gap-2 pl-2 border-l border-white/15">
              {(() => {
                const roleDisplay = user.role === 'buyer' 
                  ? 'VP Global Procurement' 
                  : user.supplier ? `${user.supplier.name} (Carrier Rep)` : 'Carrier Account Rep';
                return (
                  <div 
                    className="hidden md:flex flex-col text-right min-w-[220px] max-w-[280px] shrink-0"
                    title={`${user.full_name} · ${roleDisplay}`}
                  >
                    <span className="text-xs font-mono font-medium text-meridian-ivory truncate">
                      {user.full_name}
                    </span>
                    <span className="text-[10px] font-mono text-white/60 truncate">
                      {roleDisplay}
                    </span>
                  </div>
                );
              })()}
              <button
                onClick={logout}
                className="p-1 text-white/60 hover:text-meridian-orange transition-colors shrink-0"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="px-2.5 py-1 text-xs font-mono bg-meridian-lime text-meridian-graphite font-bold uppercase tracking-wider hover:opacity-90"
            >
              Sign In
            </Link>
          )}
        </div>

      </div>
    </header>
  );
};
