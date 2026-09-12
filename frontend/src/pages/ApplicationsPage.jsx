import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  Send,
  CheckCircle2,
  Clock,
  ExternalLink,
  Edit3,
  Sparkles,
  ShieldCheck,
  FileText,
  HelpCircle,
  Check,
  X,
  AlertTriangle,
  ChevronRight,
} from 'lucide-react';

export function ApplicationsPage({ activeJobIdForPreparation, onClearActiveJob }) {
  const [applications, setApplications] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedApp, setSelectedApp] = useState(null);

  // Edit fields in drawer
  const [coverLetterDraft, setCoverLetterDraft] = useState('');
  const [answersDraft, setAnswersDraft] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isPreparingNew, setIsPreparingNew] = useState(false);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const res = await api.getApplications({
        status: statusFilter || undefined,
        limit: 50,
      });
      setApplications(res.items || []);
    } catch (err) {
      console.error('Failed to load applications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApplications();
  }, [statusFilter]);

  // Handle incoming prepare request from jobs page / dashboard
  useEffect(() => {
    if (activeJobIdForPreparation) {
      handlePrepare(activeJobIdForPreparation);
    }
  }, [activeJobIdForPreparation]);

  const handlePrepare = async (jobId) => {
    setIsPreparingNew(true);
    try {
      const app = await api.prepareApplication(jobId);
      await fetchApplications();
      openApplicationDrawer(app);
      if (onClearActiveJob) onClearActiveJob();
    } catch (err) {
      alert('Failed to prepare application: ' + err.message);
    } finally {
      setIsPreparingNew(false);
    }
  };

  const openApplicationDrawer = (app) => {
    setSelectedApp(app);
    setCoverLetterDraft(app.cover_letter || '');
    setAnswersDraft(app.answers || []);
  };

  const handleApprove = async () => {
    if (!selectedApp) return;
    setIsSaving(true);
    try {
      const updated = await api.approveApplication(selectedApp.id, {
        cover_letter: coverLetterDraft,
        answers: answersDraft,
      });
      setSelectedApp(updated);
      fetchApplications();
    } catch (err) {
      alert('Approval failed: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleMarkSubmitted = async () => {
    if (!selectedApp) return;
    setIsSaving(true);
    try {
      const updated = await api.markApplicationSubmitted(selectedApp.id, {
        notes: 'Submitted via company career portal with AI prepared package',
      });
      setSelectedApp(updated);
      fetchApplications();
    } catch (err) {
      alert('Failed to mark as submitted: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleStatusChange = async (newStatus) => {
    if (!selectedApp) return;
    try {
      const updated = await api.updateApplicationStatus(selectedApp.id, newStatus);
      setSelectedApp(updated);
      fetchApplications();
    } catch (err) {
      alert('Status update failed: ' + err.message);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'READY_FOR_REVIEW':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
            Ready For Review
          </span>
        );
      case 'APPROVED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
            Approved by You
          </span>
        );
      case 'SUBMITTED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            Submitted
          </span>
        );
      case 'INTERVIEW':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/30">
            Interviewing
          </span>
        );
      case 'REJECTED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            Rejected
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>Application Management & Approvals</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono">
              {applications.length} Packages
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Strict human-in-the-loop review. Inspect tailored cover letters & custom Q&A before submitting.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-xl text-xs">
          {[
            { id: '', label: 'All' },
            { id: 'READY_FOR_REVIEW', label: 'Review Queue' },
            { id: 'APPROVED', label: 'Approved' },
            { id: 'SUBMITTED', label: 'Submitted' },
            { id: 'INTERVIEW', label: 'Interviews' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                statusFilter === tab.id
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {isPreparingNew && (
        <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 flex items-center gap-3 animate-pulse">
          <Sparkles className="w-5 h-5 text-emerald-400 animate-spin" />
          <p className="text-xs font-semibold text-emerald-300">
            AI is analyzing requirements, generating tailored cover letter, and synthesizing screening Q&A answers...
          </p>
        </div>
      )}

      {/* Applications List */}
      {loading ? (
        <div className="p-12 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : applications.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-2xl border border-dashed border-slate-800">
          <Send className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-300">No applications in this view</p>
          <p className="text-xs text-slate-500 mt-1">
            Browse discovered jobs and click "Prepare Application" to generate customized packages.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {applications.map((app) => (
            <div
              key={app.id}
              onClick={() => openApplicationDrawer(app)}
              className={`glass-card p-5 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer hover:border-emerald-500/40 transition-all ${
                selectedApp?.id === app.id ? 'border-emerald-500/60 bg-emerald-950/10' : ''
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center gap-3">
                  {getStatusBadge(app.status)}
                  <span className="text-xs text-slate-500">
                    Created {new Date(app.created_at).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="font-bold text-base text-slate-100">{app.job?.title || 'Job Title'}</h3>
                <p className="text-xs text-slate-400">
                  <span className="font-medium text-slate-300">{app.job?.company}</span> • {app.job?.location || 'Remote'}
                </p>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right hidden sm:block">
                  <span className="text-[11px] text-slate-400 block font-mono">
                    {app.answers?.length || 0} Screening Answers
                  </span>
                  <span className="text-[11px] text-emerald-400/90 font-medium">Cover Letter Ready</span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      openApplicationDrawer(app);
                    }}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-colors"
                  >
                    <span>Inspect Package</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Human-In-The-Loop Review Drawer / Modal */}
      {selectedApp && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex justify-end">
          <div className="bg-slate-900 border-l border-slate-800 w-full max-w-3xl h-screen flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-300">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-800 flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  {getStatusBadge(selectedApp.status)}
                  <span className="text-xs font-mono text-slate-400">Application #{selectedApp.id}</span>
                </div>
                <h3 className="font-bold text-lg text-white">{selectedApp.job?.title}</h3>
                <p className="text-xs text-slate-400">{selectedApp.job?.company} • {selectedApp.job?.location}</p>
              </div>

              <button
                onClick={() => setSelectedApp(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6 text-xs">
              {/* Compliance / Human Verification notice */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-3">
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  Review and customize the tailored materials below. You maintain complete control over every sentence before approving.
                </p>
              </div>

              {/* Cover Letter Editor */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    <span>AI Tailored Cover Letter</span>
                  </label>
                  <span className="text-[11px] font-mono text-slate-500">
                    {coverLetterDraft.split(/\s+/).filter(Boolean).length} words
                  </span>
                </div>
                <textarea
                  rows={10}
                  value={coverLetterDraft}
                  onChange={(e) => setCoverLetterDraft(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-slate-200 text-xs leading-relaxed focus:outline-none focus:border-emerald-500 font-mono"
                  placeholder="Cover letter contents..."
                />
              </div>

              {/* Screening Q&A Generator */}
              <div className="space-y-3">
                <label className="font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Custom Screening Questions & Answers</span>
                </label>

                {answersDraft.length === 0 ? (
                  <p className="text-slate-500 italic p-3 bg-slate-950 rounded-xl border border-slate-800">
                    No custom questions detected for this position.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {answersDraft.map((ans, idx) => (
                      <div key={idx} className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
                        <p className="font-semibold text-slate-200">{ans.question}</p>
                        <textarea
                          rows={3}
                          value={ans.answer}
                          onChange={(e) => {
                            const newAnswers = [...answersDraft];
                            newAnswers[idx].answer = e.target.value;
                            setAnswersDraft(newAnswers);
                          }}
                          className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-2 text-slate-300 text-xs focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Status Selector */}
              <div className="pt-2">
                <label className="font-bold text-slate-400 uppercase tracking-wider block mb-2">Update Stage</label>
                <div className="flex flex-wrap gap-2">
                  {['READY_FOR_REVIEW', 'APPROVED', 'SUBMITTED', 'INTERVIEW', 'REJECTED'].map((st) => (
                    <button
                      key={st}
                      onClick={() => handleStatusChange(st)}
                      className={`px-3 py-1 rounded-lg text-xs font-medium border ${
                        selectedApp.status === st
                          ? 'bg-slate-700 text-white border-slate-500'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-6 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-3">
              {selectedApp.job?.external_url && (
                <a
                  href={selectedApp.job.external_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium flex items-center gap-1.5 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Open Portal</span>
                </a>
              )}

              <div className="flex items-center gap-3">
                <button
                  disabled={isSaving}
                  onClick={handleApprove}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-500/20 flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Approve Changes</span>
                </button>

                <button
                  disabled={isSaving}
                  onClick={handleMarkSubmitted}
                  className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-500/20 flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Mark as Submitted</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
