import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Bell,
  CheckCircle2,
  AlertCircle,
  Play,
  RotateCw,
  LogOut,
  User as UserIcon,
} from 'lucide-react';

export function Header({ onRefreshNeeded }) {
  const { user, logout } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [isRunningAutomation, setIsRunningAutomation] = useState(false);
  const [automationSuccessMsg, setAutomationSuccessMsg] = useState('');

  const fetchNotifications = async () => {
    try {
      const res = await api.getNotifications();
      if (res && res.items) {
        setNotifications(res.items);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, []);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const handleRunNow = async () => {
    setIsRunningAutomation(true);
    setAutomationSuccessMsg('');
    try {
      const res = await api.triggerAutomationRun();
      setAutomationSuccessMsg(`Discovered ${res.jobs_discovered} jobs (${res.matches_created} high matches)`);
      if (onRefreshNeeded) onRefreshNeeded();
      fetchNotifications();
    } catch (err) {
      alert('Error running automation: ' + err.message);
    } finally {
      setIsRunningAutomation(false);
      setTimeout(() => setAutomationSuccessMsg(''), 5000);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markNotificationsRead();
      fetchNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <header className="h-16 bg-[#0B0F19]/80 backdrop-blur-md border-b border-slate-800 px-6 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center gap-4">
        {/* Live Status indicator */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-medium text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span>Agent Online & Monitoring</span>
        </div>

        {automationSuccessMsg && (
          <span className="text-xs text-emerald-300 bg-emerald-950/60 border border-emerald-500/30 px-3 py-1 rounded-md animate-fade-in flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {automationSuccessMsg}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Trigger Instant Job Scan */}
        <button
          onClick={handleRunNow}
          disabled={isRunningAutomation}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-all disabled:opacity-50"
          title="Trigger instantaneous live RSS and API job discovery and AI match scoring"
        >
          {isRunningAutomation ? (
            <RotateCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
          )}
          <span>{isRunningAutomation ? 'Scanning...' : 'Scan Jobs Now'}</span>
        </button>

        {/* Notifications Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 relative transition-colors"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-[#0B0F19]"></span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 rounded-xl bg-slate-900 border border-slate-800 shadow-2xl p-4 z-50 animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  Live Notifications ({unreadCount})
                </h4>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="text-[11px] text-emerald-400 hover:underline"
                  >
                    Mark read
                  </button>
                )}
              </div>

              <div className="mt-3 max-h-64 overflow-y-auto space-y-2 text-xs">
                {notifications.length === 0 ? (
                  <p className="text-slate-500 py-4 text-center">No notifications</p>
                ) : (
                  notifications.slice(0, 10).map((n) => (
                    <div
                      key={n.id}
                      className={`p-2.5 rounded-lg border ${
                        n.is_read
                          ? 'bg-slate-900/40 border-slate-800/60 text-slate-400'
                          : 'bg-emerald-950/20 border-emerald-500/20 text-slate-200'
                      }`}
                    >
                      <p className="font-medium text-slate-200">{n.title}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">{n.message}</p>
                      <p className="text-[10px] text-slate-500 mt-1">
                        {new Date(n.created_at).toLocaleTimeString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Info & Logout */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-semibold text-xs">
              {user?.email ? user.email.slice(0, 2).toUpperCase() : <UserIcon className="w-4 h-4" />}
            </div>
            <div className="hidden md:block">
              <p className="text-xs font-medium text-slate-200 leading-tight">
                {user?.profile?.full_name || user?.email?.split('@')[0] || 'User'}
              </p>
              <p className="text-[10px] text-slate-400 truncate max-w-[120px]">{user?.email}</p>
            </div>
          </div>

          <button
            onClick={logout}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800/80 transition-colors"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
