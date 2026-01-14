'use client';

import { useState, useEffect } from 'react';
import { 
  Shield, MapPin, AlertTriangle, CheckCircle, XCircle, ArrowLeft, 
  Plus, Trash2, ToggleLeft, ToggleRight, RefreshCw, Download,
  Radio, Rss, MessageCircle, Youtube, Hash, Instagram, Loader2,
  ChevronDown, Settings, Database
} from 'lucide-react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

type EventType = 'protest' | 'police_presence' | 'strike' | 'clash' | 'arrest';
type SourceType = 'telegram' | 'rss' | 'twitter' | 'youtube' | 'reddit' | 'instagram';
type TabType = 'events' | 'sources';

interface FormData {
  title: string;
  description: string;
  latitude: string;
  longitude: string;
  intensity: number;
  event_type: EventType;
  verified: boolean;
  source_url: string;
  admin_key: string;
}

interface SourceFormData {
  source_type: SourceType;
  identifier: string;
  name: string;
  url: string;
  reliability_score: number;
  priority: number;
  category: string;
  notes: string;
}

interface DataSource {
  id: number;
  source_type: string;
  identifier: string;
  name: string;
  url?: string;
  reliability_score: number;
  priority: number;
  category?: string;
  is_active: boolean;
  last_fetch_at?: string;
  last_fetch_status?: string;
  error_count?: number;
  notes?: string;
}

const sourceTypeConfig: Record<SourceType, { icon: typeof Radio; label: string; color: string; placeholder: string }> = {
  telegram: { icon: MessageCircle, label: 'Telegram', color: 'bg-blue-500', placeholder: 'channel_name' },
  rss: { icon: Rss, label: 'RSS Feed', color: 'bg-orange-500', placeholder: 'feed_id' },
  twitter: { icon: Radio, label: 'Twitter/X', color: 'bg-slate-600', placeholder: 'username' },
  youtube: { icon: Youtube, label: 'YouTube', color: 'bg-red-500', placeholder: 'channel_id' },
  reddit: { icon: Hash, label: 'Reddit', color: 'bg-orange-600', placeholder: 'subreddit' },
  instagram: { icon: Instagram, label: 'Instagram', color: 'bg-pink-500', placeholder: 'username' },
};

const categoryOptions = [
  { value: 'news', label: '📰 News' },
  { value: 'human_rights', label: '⚖️ Human Rights' },
  { value: 'activist', label: '✊ Activist' },
  { value: 'osint', label: '🔍 OSINT' },
  { value: 'citizen_journalism', label: '📱 Citizen Journalism' },
  { value: 'government', label: '🏛️ Government' },
  { value: 'other', label: '📌 Other' },
];

export default function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState('');
  const [activeTab, setActiveTab] = useState<TabType>('sources');
  const [status, setStatus] = useState<{ type: 'success' | 'error' | null; message: string }>({ type: null, message: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Event form state
  const [formData, setFormData] = useState<FormData>({
    title: '',
    description: '',
    latitude: '',
    longitude: '',
    intensity: 3,
    event_type: 'protest',
    verified: true,
    source_url: '',
    admin_key: '',
  });
  
  // Source management state
  const [sources, setSources] = useState<DataSource[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [showAddSource, setShowAddSource] = useState(false);
  const [sourceForm, setSourceForm] = useState<SourceFormData>({
    source_type: 'telegram',
    identifier: '',
    name: '',
    url: '',
    reliability_score: 0.7,
    priority: 2,
    category: 'news',
    notes: '',
  });

  // Fetch sources when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchSources();
    }
  }, [isAuthenticated, adminKey]);

  const fetchSources = async () => {
    setSourcesLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/sources?admin_key=${encodeURIComponent(adminKey)}`);
      const data = await res.json();
      if (data.sources) {
        setSources(data.sources);
      }
    } catch (error) {
      console.error('Failed to fetch sources:', error);
    } finally {
      setSourcesLoading(false);
    }
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (adminKey.length > 0) {
      setFormData(prev => ({ ...prev, admin_key: adminKey }));
      setIsAuthenticated(true);
    }
  };

  const handleEventSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setStatus({ type: null, message: '' });

    try {
      const response = await fetch(`${API_URL}/api/admin/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          latitude: parseFloat(formData.latitude),
          longitude: parseFloat(formData.longitude),
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setStatus({ type: 'success', message: `Event created successfully! ID: ${data.event_id}` });
        setFormData(prev => ({
          ...prev,
          title: '', description: '', latitude: '', longitude: '',
          intensity: 3, event_type: 'protest', verified: true, source_url: '',
        }));
      } else {
        setStatus({ type: 'error', message: data.detail || 'Failed to create event' });
      }
    } catch {
      setStatus({ type: 'error', message: 'Network error. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSourceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setStatus({ type: null, message: '' });

    try {
      const response = await fetch(`${API_URL}/api/admin/sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...sourceForm,
          admin_key: adminKey,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setStatus({ type: 'success', message: data.message || 'Source added successfully!' });
        setSourceForm({
          source_type: 'telegram', identifier: '', name: '', url: '',
          reliability_score: 0.7, priority: 2, category: 'news', notes: '',
        });
        setShowAddSource(false);
        fetchSources();
      } else {
        setStatus({ type: 'error', message: data.detail || 'Failed to add source' });
      }
    } catch {
      setStatus({ type: 'error', message: 'Network error. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleSource = async (sourceId: number) => {
    try {
      const response = await fetch(`${API_URL}/api/admin/sources/${sourceId}/toggle?admin_key=${encodeURIComponent(adminKey)}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        fetchSources();
      }
    } catch (error) {
      console.error('Failed to toggle source:', error);
    }
  };

  const handleDeleteSource = async (sourceId: number) => {
    if (!confirm('Are you sure you want to delete this source?')) return;
    
    try {
      const response = await fetch(`${API_URL}/api/admin/sources/${sourceId}?admin_key=${encodeURIComponent(adminKey)}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setStatus({ type: 'success', message: 'Source deleted successfully' });
        fetchSources();
      }
    } catch (error) {
      console.error('Failed to delete source:', error);
    }
  };

  const handleImportDefaults = async () => {
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/admin/sources/import-defaults?admin_key=${encodeURIComponent(adminKey)}`, {
        method: 'POST',
      });
      
      const data = await response.json();
      if (response.ok) {
        setStatus({ type: 'success', message: data.message });
        fetchSources();
      } else {
        setStatus({ type: 'error', message: data.detail || 'Import failed' });
      }
    } catch {
      setStatus({ type: 'error', message: 'Network error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredSources = sources.filter(s => {
    if (sourceFilter !== 'all' && s.source_type !== sourceFilter) return false;
    if (statusFilter === 'active' && !s.is_active) return false;
    if (statusFilter === 'inactive' && s.is_active) return false;
    return true;
  });

  const eventTypes: { value: EventType; label: string; color: string }[] = [
    { value: 'protest', label: '✊ Protest', color: 'bg-red-500' },
    { value: 'police_presence', label: '🚨 Police Presence', color: 'bg-blue-500' },
    { value: 'strike', label: '🛑 Strike', color: 'bg-yellow-500' },
    { value: 'clash', label: '⚡ Clash', color: 'bg-orange-500' },
    { value: 'arrest', label: '🔒 Arrest', color: 'bg-purple-500' },
  ];

  // Login screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="bg-slate-800/80 backdrop-blur-xl border border-slate-700 rounded-2xl p-8 shadow-2xl">
            <div className="flex items-center justify-center mb-6">
              <div className="p-3 bg-amber-500/20 rounded-full">
                <Shield className="w-8 h-8 text-amber-400" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-white text-center mb-2">Admin Access</h1>
            <p className="text-slate-400 text-center mb-6">Enter your admin key to continue</p>
            
            <form onSubmit={handleLogin} className="space-y-4">
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                placeholder="Admin Key"
                className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                required
              />
              <button
                type="submit"
                className="w-full py-3 bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold rounded-xl transition-colors"
              >
                Access Admin Panel
              </button>
            </form>
            
            <Link href="/" className="flex items-center justify-center gap-2 mt-6 text-slate-400 hover:text-white transition-colors">
              <ArrowLeft className="w-4 h-4" />
              Back to Map
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Admin panel
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Shield className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Admin Panel</h1>
              <p className="text-sm text-slate-400">Manage events & data sources</p>
            </div>
          </div>
          <Link
            href="/"
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Map
          </Link>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('sources')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === 'sources'
                ? 'bg-amber-500 text-slate-900'
                : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <Database className="w-4 h-4" />
            Data Sources
          </button>
          <button
            onClick={() => setActiveTab('events')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === 'events'
                ? 'bg-amber-500 text-slate-900'
                : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <MapPin className="w-4 h-4" />
            Add Event
          </button>
        </div>

        {/* Status Message */}
        {status.type && (
          <div
            className={`mb-6 p-4 rounded-xl flex items-center gap-3 ${
              status.type === 'success'
                ? 'bg-green-500/20 border border-green-500/50 text-green-300'
                : 'bg-red-500/20 border border-red-500/50 text-red-300'
            }`}
          >
            {status.type === 'success' ? (
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
            ) : (
              <XCircle className="w-5 h-5 flex-shrink-0" />
            )}
            <span>{status.message}</span>
            <button onClick={() => setStatus({ type: null, message: '' })} className="ml-auto">
              <XCircle className="w-4 h-4 opacity-60 hover:opacity-100" />
            </button>
          </div>
        )}

        {/* Sources Tab */}
        {activeTab === 'sources' && (
          <div className="space-y-6">
            {/* Source Controls */}
            <div className="flex flex-col gap-4">
              {/* Status Filter */}
              <div className="flex gap-2 p-1 bg-slate-800/50 rounded-lg w-fit">
                <button 
                  onClick={() => setStatusFilter('all')} 
                  className={`px-4 py-1.5 rounded-md text-xs font-bold uppercase transition-all ${statusFilter === 'all' ? 'bg-slate-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}
                >
                  All
                </button>
                <button 
                  onClick={() => setStatusFilter('inactive')} 
                  className={`px-4 py-1.5 rounded-md text-xs font-bold uppercase transition-all flex items-center gap-2 ${statusFilter === 'inactive' ? 'bg-yellow-500/20 text-yellow-400 shadow-sm border border-yellow-500/20' : 'text-slate-400 hover:text-yellow-400'}`}
                >
                  <AlertTriangle className="w-3 h-3" />
                  Pending ({sources.filter(s => !s.is_active).length})
                </button>
                <button 
                  onClick={() => setStatusFilter('active')} 
                  className={`px-4 py-1.5 rounded-md text-xs font-bold uppercase transition-all ${statusFilter === 'active' ? 'bg-green-500/20 text-green-400 shadow-sm border border-green-500/20' : 'text-slate-400 hover:text-green-400'}`}
                >
                  Active
                </button>
              </div>

              <div className="flex flex-wrap gap-3 items-center justify-between">
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => setSourceFilter('all')}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                      sourceFilter === 'all' ? 'bg-amber-500 text-slate-900' : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                    }`}
                  >
                    All Types
                  </button>
                  {Object.entries(sourceTypeConfig).map(([type, config]) => {
                    const count = sources.filter(s => s.source_type === type).length;
                    return (
                      <button
                        key={type}
                        onClick={() => setSourceFilter(type)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all ${
                          sourceFilter === type ? `${config.color} text-white` : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                        }`}
                      >
                        <config.icon className="w-3.5 h-3.5" />
                        {config.label} ({count})
                      </button>
                    );
                  })}
                </div>
                
                <div className="flex gap-2">
                <button
                  onClick={handleImportDefaults}
                  disabled={isSubmitting}
                  className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Import Defaults
                </button>
                <button
                  onClick={fetchSources}
                  disabled={sourcesLoading}
                  className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
                >
                  <RefreshCw className={`w-4 h-4 ${sourcesLoading ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                <button
                  onClick={() => setShowAddSource(!showAddSource)}
                  className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Source
                </button>
              </div>
            </div>
          </div>

            {/* Add Source Form */}
            {showAddSource && (
              <form onSubmit={handleSourceSubmit} className="bg-slate-800/80 backdrop-blur-xl border border-slate-700 rounded-2xl p-6 space-y-4">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Plus className="w-5 h-5 text-green-400" />
                  Add New Source
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Source Type */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Source Type</label>
                    <div className="grid grid-cols-3 gap-2">
                      {Object.entries(sourceTypeConfig).map(([type, config]) => (
                        <button
                          key={type}
                          type="button"
                          onClick={() => setSourceForm(prev => ({ ...prev, source_type: type as SourceType }))}
                          className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-all ${
                            sourceForm.source_type === type
                              ? `${config.color} text-white`
                              : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                          }`}
                        >
                          <config.icon className="w-4 h-4" />
                          {config.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {/* Category */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Category</label>
                    <select
                      value={sourceForm.category}
                      onChange={(e) => setSourceForm(prev => ({ ...prev, category: e.target.value }))}
                      className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-amber-500"
                    >
                      {categoryOptions.map(cat => (
                        <option key={cat.value} value={cat.value}>{cat.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Identifier */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Identifier <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={sourceForm.identifier}
                      onChange={(e) => setSourceForm(prev => ({ ...prev, identifier: e.target.value }))}
                      placeholder={sourceTypeConfig[sourceForm.source_type].placeholder}
                      className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      required
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      {sourceForm.source_type === 'telegram' && 'Channel username without @'}
                      {sourceForm.source_type === 'rss' && 'Unique ID for this feed'}
                      {sourceForm.source_type === 'twitter' && 'Twitter handle without @'}
                      {sourceForm.source_type === 'youtube' && 'Channel identifier'}
                      {sourceForm.source_type === 'reddit' && 'Subreddit name without r/'}
                      {sourceForm.source_type === 'instagram' && 'Instagram username'}
                    </p>
                  </div>
                  
                  {/* Display Name */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Display Name</label>
                    <input
                      type="text"
                      value={sourceForm.name}
                      onChange={(e) => setSourceForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Human-readable name"
                      className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
                    />
                  </div>
                </div>

                {/* URL (for RSS) */}
                {(sourceForm.source_type === 'rss' || sourceForm.source_type === 'youtube') && (
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      {sourceForm.source_type === 'rss' ? 'Feed URL' : 'YouTube Channel ID'} <span className="text-red-400">*</span>
                    </label>
                    <input
                      type={sourceForm.source_type === 'rss' ? 'url' : 'text'}
                      value={sourceForm.url}
                      onChange={(e) => setSourceForm(prev => ({ ...prev, url: e.target.value }))}
                      placeholder={sourceForm.source_type === 'rss' ? 'https://example.com/feed.xml' : 'UCxxxxxxxxxxxxxx'}
                      className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      required={sourceForm.source_type === 'rss'}
                    />
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Reliability Score */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Reliability: {Math.round(sourceForm.reliability_score * 100)}%
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={sourceForm.reliability_score * 100}
                      onChange={(e) => setSourceForm(prev => ({ ...prev, reliability_score: parseInt(e.target.value) / 100 }))}
                      className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                    />
                  </div>
                  
                  {/* Priority */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Priority</label>
                    <div className="flex gap-2">
                      {[1, 2, 3].map(p => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setSourceForm(prev => ({ ...prev, priority: p }))}
                          className={`flex-1 py-2 rounded-lg text-sm transition-all ${
                            sourceForm.priority === p
                              ? p === 1 ? 'bg-red-500 text-white' : p === 2 ? 'bg-yellow-500 text-slate-900' : 'bg-slate-500 text-white'
                              : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                          }`}
                        >
                          {p === 1 ? '🔴 High' : p === 2 ? '🟡 Medium' : '⚪ Low'}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Notes */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Notes</label>
                  <textarea
                    value={sourceForm.notes}
                    onChange={(e) => setSourceForm(prev => ({ ...prev, notes: e.target.value }))}
                    placeholder="Optional notes about this source..."
                    rows={2}
                    className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="flex-1 py-3 bg-green-600 hover:bg-green-700 disabled:bg-slate-600 text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
                  >
                    {isSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
                    Add Source
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAddSource(false)}
                    className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-xl transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            {/* Sources List */}
            <div className="bg-slate-800/80 backdrop-blur-xl border border-slate-700 rounded-2xl overflow-hidden">
              {sourcesLoading ? (
                <div className="flex items-center justify-center p-12">
                  <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
                </div>
              ) : filteredSources.length === 0 ? (
                <div className="text-center p-12 text-slate-400">
                  <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p className="text-lg mb-2">No sources configured</p>
                  <p className="text-sm">Click &quot;Import Defaults&quot; to load built-in sources or add new ones manually.</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-700/50">
                  {filteredSources.map(source => {
                    const config = sourceTypeConfig[source.source_type as SourceType] || sourceTypeConfig.rss;
                    const IconComponent = config.icon;
                    
                    return (
                      <div
                        key={source.id}
                        className={`p-4 flex items-center gap-4 transition-colors ${
                          source.is_active ? 'hover:bg-slate-700/30' : 'opacity-50 bg-slate-900/30'
                        }`}
                      >
                        <div className={`p-2 rounded-lg ${config.color}`}>
                          <IconComponent className="w-5 h-5 text-white" />
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-white truncate">{source.name || source.identifier}</span>
                            { !source.is_active && (
                              <span className="text-[10px] px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded font-bold uppercase flex items-center gap-1 border border-yellow-500/30">
                                <AlertTriangle className="w-3 h-3" /> Pending
                              </span>
                            )}
                            {source.category && (
                              <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded-full">
                                {source.category}
                              </span>
                            )}
                            {source.priority === 1 && (
                              <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-300 rounded-full">High Priority</span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-sm text-slate-400">
                            <span>{source.source_type}/{source.identifier}</span>
                            <span>•</span>
                            <span>{Math.round(source.reliability_score * 100)}% reliable</span>
                            {source.last_fetch_status && (
                              <>
                                <span>•</span>
                                <span className={source.last_fetch_status === 'success' ? 'text-green-400' : 'text-red-400'}>
                                  {source.last_fetch_status}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleToggleSource(source.id)}
                            className={`p-2 rounded-lg transition-colors ${
                              source.is_active 
                                ? 'text-green-400 hover:bg-green-500/20' 
                                : 'text-slate-500 hover:bg-slate-700'
                            }`}
                            title={source.is_active ? 'Deactivate' : 'Activate'}
                          >
                            {source.is_active ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
                          </button>
                          <button
                            onClick={() => handleDeleteSource(source.id)}
                            className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/20 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Events Tab */}
        {activeTab === 'events' && (
          <form onSubmit={handleEventSubmit} className="bg-slate-800/80 backdrop-blur-xl border border-slate-700 rounded-2xl p-6 space-y-6">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Title <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                placeholder="e.g., Protest in Azadi Square"
                className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
                required
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Details about the event..."
                rows={3}
                className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
              />
            </div>

            {/* Location */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  <MapPin className="w-4 h-4 inline mr-1" />
                  Latitude <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  step="any"
                  value={formData.latitude}
                  onChange={(e) => setFormData(prev => ({ ...prev, latitude: e.target.value }))}
                  placeholder="35.6892"
                  className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Longitude <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  step="any"
                  value={formData.longitude}
                  onChange={(e) => setFormData(prev => ({ ...prev, longitude: e.target.value }))}
                  placeholder="51.3890"
                  className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  required
                />
              </div>
            </div>

            {/* Event Type */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Event Type</label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {eventTypes.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, event_type: type.value }))}
                    className={`px-4 py-2 rounded-lg border transition-all ${
                      formData.event_type === type.value
                        ? `${type.color} border-transparent text-white`
                        : 'bg-slate-700/50 border-slate-600 text-slate-300 hover:border-slate-500'
                    }`}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Intensity */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Intensity: {formData.intensity}/5
              </label>
              <input
                type="range"
                min="1"
                max="5"
                value={formData.intensity}
                onChange={(e) => setFormData(prev => ({ ...prev, intensity: parseInt(e.target.value) }))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
              />
              <div className="flex justify-between text-xs text-slate-500 mt-1">
                <span>Low</span>
                <span>High</span>
              </div>
            </div>

            {/* Source URL */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Source URL</label>
              <input
                type="url"
                value={formData.source_url}
                onChange={(e) => setFormData(prev => ({ ...prev, source_url: e.target.value }))}
                placeholder="https://..."
                className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            {/* Verified Toggle */}
            <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-xl">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <span className="text-slate-300">Mark as Verified</span>
              </div>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, verified: !prev.verified }))}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  formData.verified ? 'bg-green-500' : 'bg-slate-600'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    formData.verified ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-4 bg-amber-500 hover:bg-amber-600 disabled:bg-slate-600 disabled:cursor-not-allowed text-slate-900 font-bold rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Event'
              )}
            </button>

            {/* Quick Reference */}
            <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-xl">
              <h3 className="text-sm font-medium text-slate-300 mb-2">📍 Common Locations</h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, latitude: '35.6892', longitude: '51.3890' }))}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors text-left"
                >
                  Tehran (35.6892, 51.3890)
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, latitude: '32.6546', longitude: '51.6680' }))}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors text-left"
                >
                  Isfahan (32.6546, 51.6680)
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, latitude: '29.5918', longitude: '52.5837' }))}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors text-left"
                >
                  Shiraz (29.5918, 52.5837)
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, latitude: '38.0800', longitude: '46.2919' }))}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors text-left"
                >
                  Tabriz (38.0800, 46.2919)
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
