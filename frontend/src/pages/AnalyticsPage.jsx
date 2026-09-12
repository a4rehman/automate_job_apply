import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  BarChart3,
  TrendingUp,
  Activity,
  CheckCircle,
  FileCheck,
  Shield,
  Layers,
  Calendar,
} from 'lucide-react';

export function AnalyticsPage() {
  const [analytics, setAnalytics] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [kpiRes, auditRes] = await Promise.all([
        api.getKPIs().catch(() => null),
        api.getAuditLogs().catch(() => ({ items: [] })),
      ]);
      setAnalytics(kpiRes);
      setAuditLogs(auditRes?.items || auditRes || []);
    } catch (err) {
      console.error('Failed to load analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-12 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span>Performance Analytics & Audit Trail</span>
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Real-time metrics, conversion rates, and immutable event compliance log.
        </p>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5 rounded-2xl space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Tracked</span>
          <p className="text-3xl font-extrabold text-white">{analytics?.total_jobs_tracked || 0}</p>
          <p className="text-[11px] text-slate-500 font-mono">Discovered through feeds</p>
        </div>

        <div className="glass-card p-5 rounded-2xl space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">High Match Pool</span>
          <p className="text-3xl font-extrabold text-emerald-400">{analytics?.high_matches_count || 0}</p>
          <p className="text-[11px] text-slate-500 font-mono">≥ 80% AI match rating</p>
        </div>

        <div className="glass-card p-5 rounded-2xl space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Submitted Total</span>
          <p className="text-3xl font-extrabold text-purple-400">{analytics?.applications_submitted || 0}</p>
          <p className="text-[11px] text-slate-500 font-mono">Human reviewed & sent</p>
        </div>

        <div className="glass-card p-5 rounded-2xl space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Interviews</span>
          <p className="text-3xl font-extrabold text-amber-400">{analytics?.interviews_scheduled || 0}</p>
          <p className="text-[11px] text-slate-500 font-mono">Positive responses</p>
        </div>
      </div>

      {/* Audit Log / Event Stream */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span>Immutable Audit & Compliance Trail</span>
          </h3>
          <span className="text-xs font-mono text-slate-500">{auditLogs.length} Events Recorded</span>
        </div>

        {auditLogs.length === 0 ? (
          <p className="text-slate-500 text-xs italic py-4 text-center">No audit logs recorded yet.</p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {auditLogs.map((log) => (
              <div
                key={log.id}
                className="p-3 bg-slate-950/80 rounded-xl border border-slate-800/80 flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-3">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-emerald-400 font-mono text-[10px] uppercase font-semibold">
                    {log.event_type}
                  </span>
                  <div>
                    <p className="text-slate-300 font-medium">{log.entity_type} #{log.entity_id}</p>
                    {log.details && (
                      <p className="text-[11px] text-slate-500 font-mono">
                        {JSON.stringify(log.details).slice(0, 80)}
                      </p>
                    )}
                  </div>
                </div>
                <span className="text-[10px] text-slate-500 font-mono shrink-0">
                  {new Date(log.timestamp).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
