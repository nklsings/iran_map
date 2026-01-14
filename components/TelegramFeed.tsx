'use client';

import React, { useEffect, useState, useCallback } from 'react';

// Unified message interface for both Telegram, Twitter, and RSS
interface FeedMessage {
  id: string;
  source: 'telegram' | 'twitter' | 'rss';
  channel: string;
  text: string;
  text_translated: string | null;
  media_url: string | null;
  media_type: string | null;
  timestamp: string;
  sentiment: string | null;
  keywords: string | null;
  locations_mentioned: string | null;
  event_type_detected: string | null;
  urgency_score: number;
  is_relevant: boolean;
  source_url?: string;
}

interface FeedResponse {
  status: string;
  messages: FeedMessage[];
  total_count: number;
  sources?: string;
  warning?: string;
}

const URGENCY_COLORS: Record<string, string> = {
  critical: 'border-red-500 bg-red-500/10',
  high: 'border-orange-500 bg-orange-500/10',
  medium: 'border-yellow-500 bg-yellow-500/10',
  low: 'border-zinc-500 bg-zinc-500/5',
};

const EVENT_TYPE_ICONS: Record<string, string> = {
  protest: '✊',
  clash: '⚔️',
  arrest: '🚔',
  strike: '🛑',
  police_presence: '🚨',
};

const SOURCE_ICONS: Record<string, string> = {
  telegram: '📱',
  twitter: '🐦',
  rss: '📰',
};

const SOURCE_COLORS: Record<string, string> = {
  telegram: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  twitter: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  rss: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
};

const CHANNEL_CATEGORIES: Record<string, string> = {
  HengawO: 'HR',
  '1500tasvir': 'Video',
  bbcpersian: 'News',
  iranintl: 'News',
  GeoConfirmed: 'OSINT',
  MahsaAlerts: 'Alert',
  HranaEnglish: 'HR',
  IranHumanRights: 'HR',
};

function getUrgencyLevel(score: number): string {
  if (score >= 0.9) return 'critical';
  if (score >= 0.7) return 'high';
  if (score >= 0.5) return 'medium';
  return 'low';
}

function formatTimeAgo(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function parseLocations(json: string | null): string[] {
  if (!json) return [];
  try {
    const arr = JSON.parse(json);
    return arr.map((loc: { city_en?: string; city?: string }) => loc.city_en || loc.city || '');
  } catch {
    return [];
  }
}

export default function TelegramFeed({
  isOpen,
  onClose,
  onLocationClick,
}: {
  isOpen: boolean;
  onClose: () => void;
  onLocationClick?: (lat: number, lon: number) => void;
}) {
  const [messages, setMessages] = useState<FeedMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string>('all'); // 'all', 'telegram', 'twitter'
  const [minUrgency, setMinUrgency] = useState(0);
  const [showTranslation, setShowTranslation] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchFeed = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        limit: '50',
        hours: '24',
        relevant_only: 'true',
        sources: selectedSource,
      });

      if (minUrgency > 0) {
        params.set('min_urgency', minUrgency.toString());
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout

      // Use unified feed endpoint
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || ''}/api/feed?${params}`,
        { signal: controller.signal }
      );
      
      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`Failed to fetch: ${res.status}`);
      }

      const data: FeedResponse = await res.json();
      
      if (data.warning) {
        console.warn('Feed warning:', data.warning);
      }
      
      setMessages(data.messages || []);
      setLastUpdate(new Date());
      
      if (data.status === 'success') {
        setError(null);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Request timed out. The feed service may be slow.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load feed');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedSource, minUrgency]);

  useEffect(() => {
    if (isOpen) {
      fetchFeed();

      // Auto-refresh every 60 seconds
      const interval = setInterval(fetchFeed, 60000);
      return () => clearInterval(interval);
    }
  }, [isOpen, fetchFeed]);

  if (!isOpen) return null;

  return (
    <div className="fixed left-0 top-0 md:top-20 h-full md:h-[calc(100vh-5rem)] w-96 bg-zinc-900/95 backdrop-blur-sm border-r border-zinc-700 z-50 flex flex-col shadow-2xl transition-all duration-300">
      {/* Header */}
      <div className="p-4 border-b border-zinc-700 flex items-center justify-between bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <span className="text-xl">📡</span>
          <h2 className="font-bold text-white">Live Feed</h2>
          {lastUpdate && (
            <span className="text-xs text-zinc-400">
              Updated {formatTimeAgo(lastUpdate.toISOString())}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-zinc-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-zinc-800"
        >
          ✕
        </button>
      </div>

      {/* Filters */}
      <div className="p-3 border-b border-zinc-700 space-y-3 bg-zinc-900/30">
        {/* Source filter buttons */}
        <div className="flex gap-1">
          {[
            { value: 'all', label: 'All', icon: '📡' },
            { value: 'telegram', label: 'Telegram', icon: '📱' },
            { value: 'twitter', label: 'Twitter', icon: '🐦' },
            { value: 'rss', label: 'RSS', icon: '📰' },
          ].map((source) => (
            <button
              key={source.value}
              onClick={() => setSelectedSource(source.value)}
              className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedSource === source.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
              }`}
            >
              <span className="mr-1">{source.icon}</span>
              {source.label}
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <select
            value={minUrgency}
            onChange={(e) => setMinUrgency(parseFloat(e.target.value))}
            className="flex-1 bg-zinc-800 border border-zinc-600 rounded-lg px-2 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="0">All Priority</option>
            <option value="0.5">Medium+</option>
            <option value="0.7">High+</option>
            <option value="0.9">Critical</option>
          </select>

          <button
            onClick={fetchFeed}
            disabled={loading}
            className="px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50 font-medium hover:bg-blue-500/10 rounded-lg transition-colors border border-zinc-700"
          >
            {loading ? '...' : '↻'}
          </button>
        </div>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer hover:text-white transition-colors">
            <input
              type="checkbox"
              checked={showTranslation}
              onChange={(e) => setShowTranslation(e.target.checked)}
              className="rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
            Show translations
          </label>
          <span className="text-xs text-zinc-500">
            {messages.length} messages
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
        {error && (
          <div className="p-4 text-center text-red-400">
            <p className="text-sm">⚠️ {error}</p>
            <button
              onClick={fetchFeed}
              className="mt-2 text-xs text-blue-400 hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {!error && messages.length === 0 && !loading && (
          <div className="p-8 text-center text-zinc-500">
            <p className="text-4xl mb-4 grayscale opacity-50">📭</p>
            <p className="font-medium">No messages found</p>
            <p className="text-xs mt-2">Try adjusting filters or wait for new data</p>
          </div>
        )}

        {messages.map((msg) => {
          const urgencyLevel = getUrgencyLevel(msg.urgency_score);
          const locations = parseLocations(msg.locations_mentioned);
          const eventIcon = EVENT_TYPE_ICONS[msg.event_type_detected || ''] || '';
          const channelCategory = CHANNEL_CATEGORIES[msg.channel?.replace('@', '') || ''] || '';
          const sourceIcon = SOURCE_ICONS[msg.source] || '📡';
          const sourceColor = SOURCE_COLORS[msg.source] || 'bg-zinc-700 text-zinc-300';

          return (
            <div
              key={msg.id}
              className={`p-4 border-l-2 border-b border-zinc-800 hover:bg-zinc-800/20 transition-colors ${URGENCY_COLORS[urgencyLevel]}`}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {/* Source badge */}
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border ${sourceColor}`}>
                    {sourceIcon}
                  </span>
                  {msg.source_url ? (
                    <a 
                      href={msg.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`text-xs font-bold font-mono hover:underline ${msg.source === 'twitter' ? 'text-sky-400 hover:text-sky-300' : msg.source === 'rss' ? 'text-orange-400 hover:text-orange-300' : 'text-blue-400 hover:text-blue-300'}`}
                    >
                      {msg.channel?.startsWith('@') ? msg.channel : `@${msg.channel}`}
                    </a>
                  ) : (
                    <span className={`text-xs font-bold font-mono ${msg.source === 'twitter' ? 'text-sky-400' : msg.source === 'rss' ? 'text-orange-400' : 'text-blue-400'}`}>
                      {msg.channel?.startsWith('@') ? msg.channel : `@${msg.channel}`}
                    </span>
                  )}
                  {channelCategory && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-zinc-700 rounded text-zinc-300 uppercase tracking-wide font-medium">
                      {channelCategory}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {msg.urgency_score >= 0.7 && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded font-bold uppercase tracking-wider">
                      URGENT
                    </span>
                  )}
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {formatTimeAgo(msg.timestamp)}
                  </span>
                </div>
              </div>

              {/* Content */}
              <div className="text-sm text-zinc-200 mb-2 leading-relaxed">
                {eventIcon && <span className="mr-1 inline-block transform -translate-y-px">{eventIcon}</span>}
                {msg.text.slice(0, 300)}
                {msg.text.length > 300 && '...'}
              </div>

              {/* Translation */}
              {showTranslation && msg.text_translated && (
                <div className="text-xs text-zinc-400 italic mb-3 pl-2 border-l-2 border-zinc-700 leading-relaxed bg-zinc-800/30 p-2 rounded-r">
                  {msg.text_translated.slice(0, 200)}
                  {msg.text_translated.length > 200 && '...'}
                </div>
              )}

              {/* Media display */}
              {msg.media_url && (
                <div className="mt-2 mb-2">
                  <a 
                    href={msg.media_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="block relative overflow-hidden rounded-lg border border-zinc-700 hover:border-zinc-500 transition-colors"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img 
                      src={msg.media_url} 
                      alt="Media" 
                      className="w-full max-h-48 object-cover bg-zinc-800"
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                    {msg.media_type === 'video' && (
                      <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                        <span className="text-4xl">▶️</span>
                      </div>
                    )}
                  </a>
                </div>
              )}

              {/* Footer info */}
              <div className="flex items-center flex-wrap gap-2 mt-2">
                {/* Locations */}
                {locations.length > 0 && locations.map((loc, i) => (
                  <button
                    key={i}
                    onClick={() => onLocationClick && onLocationClick(0, 0)}
                    className="text-[10px] px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded hover:bg-blue-500/20 transition-colors font-medium"
                  >
                    📍 {loc}
                  </button>
                ))}
                
                {/* View source link */}
                {msg.source_url && (
                  <a
                    href={msg.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] px-2 py-0.5 bg-zinc-700/50 text-zinc-400 border border-zinc-600 rounded hover:bg-zinc-600 hover:text-white transition-colors font-medium ml-auto"
                  >
                    View source →
                  </a>
                )}
              </div>
            </div>
          );
        })}

        {loading && messages.length === 0 && (
          <div className="p-12 text-center">
            <div className="animate-spin text-2xl mb-4 opacity-50">📡</div>
            <p className="text-zinc-500 text-sm">Loading feed...</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-zinc-700 bg-zinc-900/80 text-[10px] text-zinc-500 text-center font-mono">
        {messages.length} items • 
        {messages.filter(m => m.source === 'telegram').length} 📱 
        {messages.filter(m => m.source === 'twitter').length} 🐦 
        {messages.filter(m => m.source === 'rss').length} 📰
      </div>
    </div>
  );
}

