import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  Cpu,
  Settings,
  Rss,
  Play,
  CheckCircle2,
  Clock,
  ShieldCheck,
  AlertCircle,
  Save,
  RotateCw,
} from 'lucide-react';

export function AutomationPage() {
  const [settings, setSettings] = useState(null);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [settingsRes, sourcesRes] = await Promise.all([
        api.getAutomationSettings().catch(() => null),
        api.getSources().catch(() => []),
      ]);
      setSettings(settingsRes);
      setSources(sourcesRes);
    } catch (err) {
      console.error('Failed to load automation settings', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.updateAutomationSettings(settings);
      setSettings(updated);
      setStatusMsg('Automation settings successfully updated.');
      setTimeout(() => setStatusMsg(''), 4000);
    } catch (err) {
      alert('Failed to save settings: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerNow = async () => {
    setRunning(true);
    try {
      const res = await api.triggerAutomationRun();
      setStatusMsg(`Job scan completed: ${res.jobs_discovered} jobs found, ${res.matches_created} high matches evaluated.`);
      setTimeout(() => setStatusMsg(''), 5000);
    } catch (err) {
      alert('Automation scan failed: ' + err.message);
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="p-12 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>Automation & Feed Scheduler</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
              APScheduler Active
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure autonomous discovery frequency, match threshold filters, and registered feed sources.
          </p>
        </div>

        <button
          onClick={handleTriggerNow}
          disabled={running}
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition-all disabled:opacity-50"
        >
          {running ? (
            <RotateCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-white" />
          )}
          <span>{running ? 'Executing Live Scan...' : 'Trigger Instant Scan'}</span>
        </button>
      </div>

      {statusMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 flex items-center gap-2 text-xs text-emerald-300 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{statusMsg}</span>
        </div>
      )}

      {/* Settings Form */}
      <form onSubmit={handleSaveSettings} className="space-y-6 text-xs">
        {/* Scheduler Switch Card */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span>Autonomous Background Job Polling</span>
              </h3>
              <p className="text-slate-400 text-xs mt-0.5">
                Automatically fetches newly posted positions at regular intervals.
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings?.is_scheduler_enabled ?? true}
                onChange={(e) =>
                  setSettings({ ...settings, is_scheduler_enabled: e.target.checked })
                }
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
            </label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-slate-800">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Polling Interval (Minutes)
              </label>
              <select
                value={settings?.monitoring_interval_minutes || 10}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    monitoring_interval_minutes: parseInt(e.target.value),
                  })
                }
                className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
              >
                <option value={5}>Every 5 minutes (Fast)</option>
                <option value={10}>Every 10 minutes (Recommended)</option>
                <option value={30}>Every 30 minutes</option>
                <option value={60}>Every 60 minutes</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Minimum Match Score for Queueing (%)
              </label>
              <input
                type="number"
                min="0"
                max="100"
                value={settings?.min_match_score || 75}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    min_match_score: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Human In Loop & Application Preparation Rules */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Safety & Human-in-the-Loop Controls</span>
          </h3>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3.5 bg-slate-950 rounded-xl border border-slate-800">
              <div>
                <p className="font-semibold text-slate-200">Auto-Prepare High Matches</p>
                <p className="text-slate-400 text-[11px]">
                  Automatically draft customized cover letters and Q&A answers when match score ≥ threshold
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings?.auto_prepare_applications ?? true}
                onChange={(e) =>
                  setSettings({ ...settings, auto_prepare_applications: e.target.checked })
                }
                className="w-4 h-4 text-emerald-500 rounded bg-slate-800 border-slate-700 focus:ring-0"
              />
            </div>

            <div className="flex items-center justify-between p-3.5 bg-slate-950 rounded-xl border border-slate-800">
              <div>
                <p className="font-semibold text-slate-200">Require Human Approval (Strict TOS Compliance)</p>
                <p className="text-slate-400 text-[11px]">
                  Never submit an application without your explicit manual review & approval
                </p>
              </div>
              <input
                type="checkbox"
                disabled
                checked={true}
                className="w-4 h-4 text-emerald-500 rounded bg-slate-800 border-slate-700 cursor-not-allowed opacity-80"
              />
            </div>
          </div>
        </div>

        {/* Registered Feed Sources */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Rss className="w-4 h-4 text-emerald-400" />
              <span>Registered Job Source Feeds ({sources.length})</span>
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sources.map((src, i) => (
              <div
                key={i}
                className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between"
              >
                <div>
                  <p className="font-semibold text-slate-200">{src.name}</p>
                  <p className="text-[10px] text-slate-400 font-mono mt-0.5">{src.adapter_type} • {src.feed_type}</p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                  Active
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold rounded-xl shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Automation Preferences'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
