import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  TrendingUp,
  Briefcase,
  CheckCircle2,
  Clock,
  Sparkles,
  ExternalLink,
  ArrowRight,
  ShieldAlert,
  Percent,
} from 'lucide-react';

export function DashboardPage({ onNavigateToTab, onPrepareJob }) {
  const [kpis, setKpis] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [kpiRes, funnelRes, jobsRes, appsRes] = await Promise.all([
        api.getKPIs().catch(() => ({})),
        api.getFunnel().catch(() => ({})),
        api.getJobs({ limit: 5, sort_by: 'match_score' }).catch(() => ({ items: [] })),
        api.getApplications({ status: 'READY_FOR_REVIEW', limit: 3 }).catch(() => ({ items: [] })),
      ]);
      setKpis(kpiRes);
      setFunnel(funnelRes);
      setRecentJobs(jobsRes.items || []);
      setPendingApprovals(appsRes.items || []);
    } catch (err) {
      console.error('Failed to load dashboard', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[500px]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-xs text-slate-400">Loading AI intelligence analytics...</p>
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Discovered Jobs',
      value: kpis?.total_jobs_tracked ?? 0,
      sub: `${kpis?.jobs_added_today ?? 0} added today`,
      icon: Briefcase,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10 border-blue-500/20',
    },
    {
      title: 'High AI Matches (≥80%)',
      value: kpis?.high_matches_count ?? 0,
      sub: `${kpis?.average_match_score ?? 0}% avg score`,
      icon: Sparkles,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10 border-emerald-500/20',
    },
    {
      title: 'Pending Human Approval',
      value: kpis?.ready_for_review_count ?? 0,
      sub: 'Action required',
      icon: Clock,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10 border-amber-500/20',
    },
    {
      title: 'Applications Submitted',
      value: kpis?.applications_submitted ?? 0,
      sub: `${kpis?.interviews_scheduled ?? 0} interviews active`,
      icon: CheckCircle2,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10 border-purple-500/20',
    },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Hero Welcome */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-slate-900/90 to-emerald-950/40 p-6 rounded-2xl border border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>Welcome back</span>
            <span className="text-emerald-400 text-sm font-normal px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              Active Optimization
            </span>
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Your autonomous agent is monitoring job feeds, parsing requirements, tailoring resumes, and queueing high-match applications for your review.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => onNavigateToTab('jobs')}
            className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white font-medium text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-2"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Discover Top Matches</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div key={i} className="glass-card p-5 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{stat.title}</span>
                <div className={`p-2 rounded-lg border ${stat.bg}`}>
                  <Icon className={`w-4 h-4 ${stat.color}`} />
                </div>
              </div>
              <div>
                <p className="text-3xl font-extrabold text-white tracking-tight">{stat.value}</p>
                <p className="text-xs text-slate-400 mt-1 flex items-center gap-1 font-mono">
                  <span>{stat.sub}</span>
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Application Funnel & Pending Approvals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recruitment Funnel */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Application Funnel</h3>
            <span className="text-xs text-slate-400">Live conversion stats</span>
          </div>

          <div className="space-y-3 pt-2">
            {[
              { label: 'Discovered', count: funnel?.discovered || kpis?.total_jobs_tracked || 0, color: 'bg-blue-500' },
              { label: 'Match Filtered (≥75%)', count: funnel?.match_filtered || kpis?.high_matches_count || 0, color: 'bg-teal-500' },
              { label: 'Prepared Packages', count: funnel?.prepared || 0, color: 'bg-indigo-500' },
              { label: 'Approved by You', count: funnel?.approved || 0, color: 'bg-amber-500' },
              { label: 'Submitted to Company', count: funnel?.submitted || kpis?.applications_submitted || 0, color: 'bg-emerald-500' },
            ].map((step, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-slate-300">{step.label}</span>
                  <span className="font-mono text-slate-400">{step.count}</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                  <div
                    className={`${step.color} h-2 rounded-full transition-all duration-500`}
                    style={{
                      width: `${Math.max(
                        8,
                        Math.min(100, (step.count / Math.max(1, funnel?.discovered || kpis?.total_jobs_tracked || 1)) * 100)
                      )}%`,
                    }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pending Human Approvals Action Box */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                Human-In-The-Loop Approval Queue
              </h3>
            </div>
            <button
              onClick={() => onNavigateToTab('applications')}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1"
            >
              <span>View all ({pendingApprovals.length})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {pendingApprovals.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 bg-slate-900/40 rounded-xl border border-dashed border-slate-800 text-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400/80 mb-2" />
              <p className="text-sm font-medium text-slate-300">All applications approved and clear</p>
              <p className="text-xs text-slate-500 max-w-sm mt-1">
                When high-matching jobs are found, tailored cover letters & Q&A will appear here for your 1-click review.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {pendingApprovals.map((app) => (
                <div
                  key={app.id}
                  className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 flex items-center justify-between gap-4 hover:border-amber-500/30 transition-all"
                >
                  <div>
                    <h4 className="font-semibold text-sm text-slate-100">{app.job?.title || 'Job Application'}</h4>
                    <p className="text-xs text-slate-400">{app.job?.company || 'Company'}</p>
                    <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-400">
                      <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium border border-amber-500/20">
                        Ready For Review
                      </span>
                      <span>Prepared: {new Date(app.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => onNavigateToTab('applications')}
                    className="px-3.5 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-semibold rounded-lg transition-colors shrink-0"
                  >
                    Review & Submit
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top Matching Jobs */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Top AI Matching Opportunities</h3>
            <p className="text-xs text-slate-400">Ranked by semantic match against your verified resume</p>
          </div>
          <button
            onClick={() => onNavigateToTab('jobs')}
            className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1"
          >
            <span>Browse all jobs</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {recentJobs.map((job) => {
            const score = job.match?.overall_score ?? (job.match_score ?? 80);
            return (
              <div key={job.id} className="glass-card p-5 rounded-xl flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {job.source || 'Direct'}
                    </span>
                    <span
                      className={`text-xs font-bold font-mono px-2.5 py-0.5 rounded-full border ${
                        score >= 85
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : score >= 70
                          ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {Math.round(score)}% Match
                    </span>
                  </div>

                  <h4 className="font-semibold text-sm text-slate-100 mt-2 line-clamp-1">{job.title}</h4>
                  <p className="text-xs text-slate-400">{job.company} • {job.location || 'Remote'}</p>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {(job.skills_required || []).slice(0, 3).map((skill, sIdx) => (
                      <span key={sIdx} className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  {job.external_url ? (
                    <a
                      href={job.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>Original Post</span>
                    </a>
                  ) : <div />}

                  <button
                    onClick={() => {
                      if (onPrepareJob) onPrepareJob(job.id);
                      else onNavigateToTab('jobs');
                    }}
                    className="px-3 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium rounded-lg transition-colors"
                  >
                    Prepare Application
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
