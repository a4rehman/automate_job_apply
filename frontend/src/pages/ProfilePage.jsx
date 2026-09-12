import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  User,
  Upload,
  FileText,
  Plus,
  Trash2,
  Save,
  CheckCircle2,
  Sparkles,
  Briefcase,
  Layers,
  MapPin,
  DollarSign,
} from 'lucide-react';

export function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillCategory, setNewSkillCategory] = useState('TECHNICAL');
  const [newSkillYears, setNewSkillYears] = useState(3);
  const [statusMsg, setStatusMsg] = useState('');

  const loadProfile = async () => {
    setLoading(true);
    try {
      const data = await api.getProfile();
      setProfile(data);
    } catch (err) {
      console.error('Failed to load profile:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleProfileSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.updateProfile(profile);
      setProfile(updated);
      setStatusMsg('Profile successfully updated.');
      setTimeout(() => setStatusMsg(''), 4000);
    } catch (err) {
      alert('Failed to update profile: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleResumeUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingResume(true);
    try {
      const result = await api.uploadResume(file);
      setStatusMsg(`Resume parsed successfully! Extracted ${result.parsed_data?.skills?.length || 0} skills.`);
      loadProfile();
      setTimeout(() => setStatusMsg(''), 5000);
    } catch (err) {
      alert('Failed to parse resume: ' + err.message);
    } finally {
      setUploadingResume(false);
    }
  };

  const handleAddSkill = async (e) => {
    e.preventDefault();
    if (!newSkillName.trim()) return;

    try {
      await api.addSkill({
        name: newSkillName.trim(),
        category: newSkillCategory,
        years_experience: parseFloat(newSkillYears) || 1.0,
      });
      setNewSkillName('');
      loadProfile();
    } catch (err) {
      alert('Failed to add skill: ' + err.message);
    }
  };

  const handleDeleteSkill = async (skillId) => {
    try {
      await api.deleteSkill(skillId);
      loadProfile();
    } catch (err) {
      alert('Failed to delete skill: ' + err.message);
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
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span>Candidate Profile & Resume AI</span>
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Your profile and extracted skills form the semantic baseline for AI match ranking and tailoring.
        </p>
      </div>

      {statusMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 flex items-center gap-2 text-xs text-emerald-300 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{statusMsg}</span>
        </div>
      )}

      {/* Resume Upload & AI Parsing Card */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <FileText className="w-4 h-4 text-emerald-400" />
            <span>Active Resume (PDF / DOCX)</span>
          </h3>
          <label className="px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold text-xs rounded-xl shadow-md shadow-emerald-500/20 cursor-pointer flex items-center gap-1.5 transition-all">
            <Upload className="w-3.5 h-3.5" />
            <span>{uploadingResume ? 'Parsing with AI...' : 'Upload New Resume'}</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleResumeUpload}
              disabled={uploadingResume}
              className="hidden"
            />
          </label>
        </div>

        {profile?.resume ? (
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <p className="font-semibold text-slate-200 text-xs">{profile.resume.file_name}</p>
                <p className="text-[11px] text-slate-500">
                  Parsed: {new Date(profile.resume.created_at).toLocaleDateString()} • {profile.resume.file_type}
                </p>
              </div>
            </div>
            <span className="text-xs font-semibold text-emerald-400 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              AI Parsed & Active
            </span>
          </div>
        ) : (
          <div className="p-8 border border-dashed border-slate-800 rounded-xl text-center bg-slate-950/50">
            <Upload className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-xs font-semibold text-slate-300">No resume uploaded yet</p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Upload your PDF resume to let AI extract skills, work history, and calculate match scores.
            </p>
          </div>
        )}
      </div>

      {/* Skills Matrix */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-400" />
          <span>Verified Skills Matrix ({profile?.skills?.length || 0})</span>
        </h3>

        {/* Add Skill Form */}
        <form onSubmit={handleAddSkill} className="flex flex-wrap gap-2 text-xs">
          <input
            type="text"
            placeholder="Add new skill (e.g. PyTorch, Kubernetes)..."
            value={newSkillName}
            onChange={(e) => setNewSkillName(e.target.value)}
            className="flex-1 min-w-[200px] bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
          />
          <select
            value={newSkillCategory}
            onChange={(e) => setNewSkillCategory(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 rounded-lg px-3 py-2 focus:outline-none"
          >
            <option value="TECHNICAL">Technical</option>
            <option value="FRAMEWORK">Framework</option>
            <option value="TOOL">Tool / DevOps</option>
            <option value="SOFT">Soft Skill</option>
          </select>
          <input
            type="number"
            min="0.5"
            max="30"
            step="0.5"
            placeholder="Yrs"
            value={newSkillYears}
            onChange={(e) => setNewSkillYears(e.target.value)}
            className="w-16 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold rounded-lg flex items-center gap-1 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add</span>
          </button>
        </form>

        {/* Skills List */}
        <div className="flex flex-wrap gap-2 pt-2">
          {(profile?.skills || []).map((skill) => (
            <span
              key={skill.id}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs bg-slate-900 border border-slate-800 text-slate-200 group hover:border-emerald-500/40 transition-colors"
            >
              <span>{skill.name}</span>
              <span className="text-[10px] text-slate-500 font-mono">({skill.years_experience}y)</span>
              <button
                onClick={() => handleDeleteSkill(skill.id)}
                className="text-slate-500 hover:text-red-400 ml-1 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Profile Details Form */}
      <form onSubmit={handleProfileSave} className="glass-panel p-6 rounded-2xl space-y-4 text-xs">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <User className="w-4 h-4 text-emerald-400" />
          <span>Professional Profile & Target Preferences</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-400 mb-1">Full Name</label>
            <input
              type="text"
              value={profile?.full_name || ''}
              onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Current Job Title</label>
            <input
              type="text"
              value={profile?.current_title || ''}
              onChange={(e) => setProfile({ ...profile, current_title: e.target.value })}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Total Years of Experience</label>
            <input
              type="number"
              step="0.5"
              value={profile?.years_experience || 0}
              onChange={(e) =>
                setProfile({ ...profile, years_experience: parseFloat(e.target.value) || 0 })
              }
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Workplace Preference</label>
            <select
              value={profile?.remote_preference || 'REMOTE'}
              onChange={(e) => setProfile({ ...profile, remote_preference: e.target.value })}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="REMOTE">Remote Only</option>
              <option value="HYBRID">Hybrid</option>
              <option value="ONSITE">Onsite</option>
              <option value="ANY">Any / Open</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1">LinkedIn Profile URL</label>
            <input
              type="url"
              value={profile?.linkedin_url || ''}
              onChange={(e) => setProfile({ ...profile, linkedin_url: e.target.value })}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">GitHub / Portfolio URL</label>
            <input
              type="url"
              value={profile?.github_url || ''}
              onChange={(e) => setProfile({ ...profile, github_url: e.target.value })}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-slate-400 mb-1">Professional Bio / Executive Summary</label>
          <textarea
            rows={4}
            value={profile?.bio || ''}
            onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
            className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 leading-relaxed font-sans"
          />
        </div>

        <div className="flex justify-end pt-3 border-t border-slate-800">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold rounded-xl shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Profile Changes'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
