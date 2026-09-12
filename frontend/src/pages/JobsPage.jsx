import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  Search,
  Filter,
  Sparkles,
  ExternalLink,
  Plus,
  Building,
  MapPin,
  DollarSign,
  Calendar,
  CheckCircle,
  FileText,
  AlertCircle,
  X,
  Upload,
} from 'lucide-react';

export function JobsPage({ onPrepareApplication }) {
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [minMatch, setMinMatch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [workplaceFilter, setWorkplaceFilter] = useState('');

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedJobForDetails, setSelectedJobForDetails] = useState(null);
  const [analyzingJobId, setAnalyzingJobId] = useState(null);

  // Manual Job Form State
  const [newJobForm, setNewJobForm] = useState({
    title: '',
    company: '',
    location: 'Remote',
    workplace_type: 'Remote',
    employment_type: 'Full-time',
    source: 'Direct',
    external_url: '',
    description: '',
    skills_required: '',
  });

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const params = {
        search,
        min_match_score: minMatch ? parseFloat(minMatch) : undefined,
        status: statusFilter || undefined,
        source: sourceFilter || undefined,
        workplace_type: workplaceFilter || undefined,
        limit: 50,
      };
      const res = await api.getJobs(params);
      setJobs(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [minMatch, statusFilter, sourceFilter, workplaceFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchJobs();
  };

  const handleManualJobSubmit = async (e) => {
    e.preventDefault();
    try {
      const skillsArray = newJobForm.skills_required
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      await api.createJobManual({
        ...newJobForm,
        skills_required: skillsArray,
      });

      setShowAddModal(false);
      setNewJobForm({
        title: '',
        company: '',
        location: 'Remote',
        workplace_type: 'Remote',
        employment_type: 'Full-time',
        source: 'Direct',
        external_url: '',
        description: '',
        skills_required: '',
      });
      fetchJobs();
    } catch (err) {
      alert('Failed to save job: ' + err.message);
    }
  };

  const handleAnalyzeJob = async (jobId) => {
    setAnalyzingJobId(jobId);
    try {
      const match = await api.analyzeJob(jobId);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, match, match_score: match.overall_score } : j))
      );
    } catch (err) {
      alert('Analysis error: ' + err.message);
    } finally {
      setAnalyzingJobId(null);
    }
  };

  const handleStatusChange = async (jobId, newStatus) => {
    try {
      await api.updateJobStatus(jobId, newStatus);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status: newStatus } : j))
      );
    } catch (err) {
      alert('Failed to update status: ' + err.message);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>Job Opportunities</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono">
              {total} Total
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Discover feeds from RemoteOK, WeWorkRemotely, Remotive, Arbeitnow & direct imports
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3.5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Add Manual Job</span>
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="glass-panel p-4 rounded-xl flex flex-wrap items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by title, company, or skills..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900/90 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </form>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Min Match Filter */}
          <select
            value={minMatch}
            onChange={(e) => setMinMatch(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Match Scores</option>
            <option value="90">Top Matches (≥90%)</option>
            <option value="75">High Matches (≥75%)</option>
            <option value="60">Medium Matches (≥60%)</option>
          </select>

          {/* Workplace Filter */}
          <select
            value={workplaceFilter}
            onChange={(e) => setWorkplaceFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Workplace Types</option>
            <option value="Remote">Remote</option>
            <option value="Hybrid">Hybrid</option>
            <option value="Onsite">Onsite</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Statuses</option>
            <option value="DISCOVERED">Discovered</option>
            <option value="MATCHED">Matched</option>
            <option value="APPLIED">Applied</option>
            <option value="ARCHIVED">Archived</option>
          </select>
        </div>
      </div>

      {/* Jobs Grid */}
      {loading ? (
        <div className="p-12 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : jobs.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-2xl border border-dashed border-slate-800">
          <Briefcase className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-300">No jobs found matching your criteria</p>
          <p className="text-xs text-slate-500 mt-1">Try running a scan or adjusting your search filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobs.map((job) => {
            const score = job.match?.overall_score ?? (job.match_score ?? null);
            const isAnalyzing = analyzingJobId === job.id;

            return (
              <div
                key={job.id}
                className="glass-card p-5 rounded-2xl flex flex-col justify-between space-y-4 relative group"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                          {job.source || 'Direct'}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <h3 className="font-bold text-base text-slate-100 mt-1.5 line-clamp-1">{job.title}</h3>
                      <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                        <Building className="w-3.5 h-3.5 text-slate-500" />
                        <span className="font-medium text-slate-300">{job.company}</span>
                        <span>•</span>
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        <span>{job.location || 'Remote'}</span>
                      </p>
                    </div>

                    {/* Match Score Badge */}
                    <div className="shrink-0">
                      {score !== null ? (
                        <div
                          className={`flex flex-col items-center px-3 py-1.5 rounded-xl border font-mono ${
                            score >= 85
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                              : score >= 70
                              ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                              : 'bg-slate-800 border-slate-700 text-slate-400'
                          }`}
                        >
                          <span className="text-base font-extrabold">{Math.round(score)}%</span>
                          <span className="text-[9px] uppercase tracking-wider text-slate-400">Match</span>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleAnalyzeJob(job.id)}
                          disabled={isAnalyzing}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] rounded-lg border border-slate-700 flex items-center gap-1 transition-colors"
                        >
                          <Sparkles className="w-3 h-3 text-emerald-400" />
                          <span>{isAnalyzing ? 'Analyzing...' : 'Score AI'}</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Skills Tags */}
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {(job.skills_required || []).slice(0, 5).map((skill, sIdx) => {
                      const isMatching = job.match?.matching_skills?.includes(skill);
                      return (
                        <span
                          key={sIdx}
                          className={`text-[10px] px-2 py-0.5 rounded-md font-medium border ${
                            isMatching
                              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                              : 'bg-slate-800/80 text-slate-400 border-slate-700/60'
                          }`}
                        >
                          {skill}
                        </span>
                      );
                    })}
                    {(job.skills_required || []).length > 5 && (
                      <span className="text-[10px] text-slate-500 px-1 py-0.5">
                        +{job.skills_required.length - 5} more
                      </span>
                    )}
                  </div>

                  {/* Snippet */}
                  <p className="text-xs text-slate-400 line-clamp-2 mt-3 leading-relaxed">
                    {job.description}
                  </p>
                </div>

                {/* Footer Actions */}
                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {job.external_url && (
                      <a
                        href={job.external_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
                        title="Open external job posting"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                    <button
                      onClick={() => setSelectedJobForDetails(job)}
                      className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-800/60 transition-colors"
                    >
                      View Details
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() =>
                        handleStatusChange(
                          job.id,
                          job.status === 'ARCHIVED' ? 'DISCOVERED' : 'ARCHIVED'
                        )
                      }
                      className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      {job.status === 'ARCHIVED' ? 'Restore' : 'Archive'}
                    </button>

                    <button
                      onClick={() => onPrepareApplication(job.id)}
                      className="px-3.5 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Prepare Application</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Manual Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-bold text-base text-white">Add Job Opportunity Manually</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleManualJobSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Job Title *</label>
                  <input
                    type="text"
                    required
                    value={newJobForm.title}
                    onChange={(e) => setNewJobForm({ ...newJobForm, title: e.target.value })}
                    placeholder="e.g. Senior Machine Learning Engineer"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Company Name *</label>
                  <input
                    type="text"
                    required
                    value={newJobForm.company}
                    onChange={(e) => setNewJobForm({ ...newJobForm, company: e.target.value })}
                    placeholder="e.g. Anthropic"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Location</label>
                  <input
                    type="text"
                    value={newJobForm.location}
                    onChange={(e) => setNewJobForm({ ...newJobForm, location: e.target.value })}
                    placeholder="Remote or City"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Workplace</label>
                  <select
                    value={newJobForm.workplace_type}
                    onChange={(e) => setNewJobForm({ ...newJobForm, workplace_type: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="Remote">Remote</option>
                    <option value="Hybrid">Hybrid</option>
                    <option value="Onsite">Onsite</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Employment</label>
                  <select
                    value={newJobForm.employment_type}
                    onChange={(e) => setNewJobForm({ ...newJobForm, employment_type: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="Full-time">Full-time</option>
                    <option value="Contract">Contract</option>
                    <option value="Part-time">Part-time</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">External Job Posting URL</label>
                <input
                  type="url"
                  value={newJobForm.external_url}
                  onChange={(e) => setNewJobForm({ ...newJobForm, external_url: e.target.value })}
                  placeholder="https://boards.greenhouse.io/..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Required Skills (comma-separated)</label>
                <input
                  type="text"
                  value={newJobForm.skills_required}
                  onChange={(e) => setNewJobForm({ ...newJobForm, skills_required: e.target.value })}
                  placeholder="Python, PyTorch, FastAPI, Docker, LangChain"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Job Description *</label>
                <textarea
                  rows={5}
                  required
                  value={newJobForm.description}
                  onChange={(e) => setNewJobForm({ ...newJobForm, description: e.target.value })}
                  placeholder="Paste job description requirements and overview..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white font-medium rounded-lg shadow-md shadow-emerald-500/20"
                >
                  Save Job & Auto-Analyze
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Details Modal */}
      {selectedJobForDetails && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h3 className="font-bold text-lg text-white">{selectedJobForDetails.title}</h3>
                <p className="text-xs text-slate-400">{selectedJobForDetails.company} • {selectedJobForDetails.location}</p>
              </div>
              <button
                onClick={() => setSelectedJobForDetails(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* AI Match Explanation */}
            {selectedJobForDetails.match && (
              <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">AI Semantic Match Analysis</span>
                  <span className="text-sm font-mono font-bold text-emerald-300">
                    {Math.round(selectedJobForDetails.match.overall_score)}%
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {selectedJobForDetails.match.match_rationale || 'High alignment with candidate technical profile.'}
                </p>
                <div className="flex flex-wrap gap-2 pt-2">
                  <div className="text-[11px] text-emerald-400">
                    <span className="font-semibold">Matching: </span>
                    {selectedJobForDetails.match.matching_skills?.join(', ') || 'Core stack'}
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Job Description</h4>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto">
                {selectedJobForDetails.description}
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => setSelectedJobForDetails(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs"
              >
                Close
              </button>
              <button
                onClick={() => {
                  const id = selectedJobForDetails.id;
                  setSelectedJobForDetails(null);
                  onPrepareApplication(id);
                }}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white font-medium rounded-lg text-xs shadow-md shadow-emerald-500/20"
              >
                Prepare Application Package
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
