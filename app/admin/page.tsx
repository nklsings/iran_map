'use client';

import { useState } from 'react';
import { Shield, MapPin, AlertTriangle, CheckCircle, XCircle, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

type EventType = 'protest' | 'police_presence' | 'strike' | 'clash' | 'arrest';

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

export default function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState('');
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
  const [status, setStatus] = useState<{ type: 'success' | 'error' | null; message: string }>({
    type: null,
    message: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (adminKey.length > 0) {
      setFormData(prev => ({ ...prev, admin_key: adminKey }));
      setIsAuthenticated(true);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
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
        setStatus({
          type: 'success',
          message: `Event created successfully! ID: ${data.event_id}`,
        });
        // Reset form except admin_key
        setFormData(prev => ({
          ...prev,
          title: '',
          description: '',
          latitude: '',
          longitude: '',
          intensity: 3,
          event_type: 'protest',
          verified: true,
          source_url: '',
        }));
      } else {
        setStatus({
          type: 'error',
          message: data.detail || 'Failed to create event',
        });
      }
    } catch {
      setStatus({
        type: 'error',
        message: 'Network error. Please try again.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

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
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Shield className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Admin Panel</h1>
              <p className="text-sm text-slate-400">Add verified events</p>
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
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-slate-800/80 backdrop-blur-xl border border-slate-700 rounded-2xl p-6 space-y-6">
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
                <div className="w-5 h-5 border-2 border-slate-900/30 border-t-slate-900 rounded-full animate-spin" />
                Creating...
              </>
            ) : (
              'Create Event'
            )}
          </button>
        </form>

        {/* Quick Reference */}
        <div className="mt-6 p-4 bg-slate-800/50 border border-slate-700 rounded-xl">
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
      </div>
    </div>
  );
}

