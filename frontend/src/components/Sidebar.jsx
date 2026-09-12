import React from 'react';
import {
  LayoutDashboard,
  Briefcase,
  Send,
  Cpu,
  User,
  BarChart3,
  ShieldCheck,
  Zap,
} from 'lucide-react';

export function Sidebar({ currentTab, onSelectTab, pendingApprovalsCount = 0 }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'jobs', label: 'Jobs Discovery', icon: Briefcase },
    {
      id: 'applications',
      label: 'Applications',
      icon: Send,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : null,
    },
    { id: 'automation', label: 'Automation & Feeds', icon: Cpu },
    { id: 'profile', label: 'Profile & Resume', icon: User },
    { id: 'analytics', label: 'Analytics & Logs', icon: BarChart3 },
  ];

  return (
    <aside className="w-64 bg-[#0F172A] border-r border-slate-800 flex flex-col justify-between select-none shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="p-6 flex items-center gap-3 border-b border-slate-800/80">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-base tracking-tight text-white flex items-center gap-1.5">
              JobAgent <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-mono font-medium">AI</span>
            </h1>
            <p className="text-xs text-slate-400">Autonomous Career Co-Pilot</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Compliance / Policy Notice */}
      <div className="p-4 m-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-400 space-y-2">
        <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
          <ShieldCheck className="w-4 h-4" />
          <span>TOS Compliant Agent</span>
        </div>
        <p className="text-[11px] leading-relaxed text-slate-400">
          Human-in-the-loop review ensures 100% platform policy compliance. No bots, no anti-bot evasion.
        </p>
      </div>
    </aside>
  );
}
