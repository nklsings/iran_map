'use client';

import React, { useEffect, useState, useCallback } from 'react';

interface TelegramMessage {
  id: number;
  channel: string;
  message_id: string;
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
}

interface TelegramFeedResponse {
  status: string;
  messages: TelegramMessage[];
  total_count: number;
  channels: string[];
  latest_timestamp: string | null;
}

const URGENCY_COLORS: Record<string, string> = {
  critical: 'border-red-500 bg-red-500/10',
  high: 'border-orange-500 bg-orange-500/10',
  medium: 'border-yellow-500 bg-yellow-500/10',
  low: 'border-gray-500 bg-gray-500/5',
};

const EVENT_TYPE_ICONS: Record<string, string> = {
  protest: '✊',
  clash: '⚔️',
  arrest: '🚔',
  strike: '🛑',
  police_presence: '🚨',
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
  const [messages, setMessages] = useState<TelegramMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [channels, setChannels] = useState<string[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<string>('');
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
      });

      if (selectedChannel) {
        params.set('channel', selectedChannel);
      }
      if (minUrgency > 0) {
        params.set('min_urgency', minUrgency.toString());
      }

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/telegram/feed?${params}`
      );

      if (!res.ok) {
        throw new Error(`Failed to fetch: ${res.status}`);
      }

      const data: TelegramFeedResponse = await res.json();
      setMessages(data.messages);
      setChannels(data.channels);
      setLastUpdate(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load feed');
    } finally {
      setLoading(false);
    }
  }, [selectedChannel, minUrgency]);

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
    <div className="fixed left-0 top-0 h-full w-96 bg-gray-900/95 backdrop-blur-sm border-r border-gray-700 z-50 flex flex-col shadow-2xl">
      {/* Header */}
      <div className="p-4 border-b border-gray-700 flex items-center justify-between bg-gray-800/50">
        <div className="flex items-center gap-2">
          <span className="text-xl">📡</span>
          <h2 className="font-bold text-white">Live Feed</h2>
          {lastUpdate && (
            <span className="text-xs text-gray-400">
              Updated {formatTimeAgo(lastUpdate.toISOString())}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors p-1"
        >
          ✕
        </button>
      </div>

      {/* Filters */}
      <div className="p-3 border-b border-gray-700 space-y-2 bg-gray-800/30">
        <div className="flex gap-2">
          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white"
          >
            <option value="">All Channels</option>
            {channels.map((ch) => (
              <option key={ch} value={ch}>
                @{ch}
              </option>
            ))}
          </select>

          <select
            value={minUrgency}
            onChange={(e) => setMinUrgency(parseFloat(e.target.value))}
            className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white"
          >
            <option value="0">All</option>
            <option value="0.5">Medium+</option>
            <option value="0.7">High+</option>
            <option value="0.9">Critical</option>
          </select>
        </div>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={showTranslation}
              onChange={(e) => setShowTranslation(e.target.checked)}
              className="rounded border-gray-600"
            />
            Show translations
          </label>

          <button
            onClick={fetchFeed}
            disabled={loading}
            className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
          >
            {loading ? 'Loading...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="p-4 text-center text-red-400">
            <p>⚠️ {error}</p>
            <button
              onClick={fetchFeed}
              className="mt-2 text-sm text-blue-400 hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {!error && messages.length === 0 && !loading && (
          <div className="p-8 text-center text-gray-400">
            <p className="text-4xl mb-4">📭</p>
            <p>No messages found</p>
            <p className="text-sm mt-2">Try adjusting filters or wait for new data</p>
          </div>
        )}

        {messages.map((msg) => {
          const urgencyLevel = getUrgencyLevel(msg.urgency_score);
          const locations = parseLocations(msg.locations_mentioned);
          const eventIcon = EVENT_TYPE_ICONS[msg.event_type_detected || ''] || '';
          const channelCategory = CHANNEL_CATEGORIES[msg.channel] || '';

          return (
            <div
              key={msg.id}
              className={`p-3 border-l-4 border-b border-gray-700/50 ${URGENCY_COLORS[urgencyLevel]}`}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-blue-400 text-sm font-medium">
                    @{msg.channel}
                  </span>
                  {channelCategory && (
                    <span className="text-xs px-1.5 py-0.5 bg-gray-700 rounded text-gray-300">
                      {channelCategory}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {msg.urgency_score >= 0.7 && (
                    <span className="text-xs px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded">
                      {(msg.urgency_score * 100).toFixed(0)}% urgent
                    </span>
                  )}
                  <span className="text-xs text-gray-500">
                    {formatTimeAgo(msg.timestamp)}
                  </span>
                </div>
              </div>

              {/* Content */}
              <div className="text-sm text-gray-200 mb-2">
                {eventIcon && <span className="mr-1">{eventIcon}</span>}
                {msg.text.slice(0, 300)}
                {msg.text.length > 300 && '...'}
              </div>

              {/* Translation */}
              {showTranslation && msg.text_translated && (
                <div className="text-sm text-gray-400 italic mb-2 pl-2 border-l-2 border-gray-600">
                  {msg.text_translated.slice(0, 200)}
                  {msg.text_translated.length > 200 && '...'}
                </div>
              )}

              {/* Locations */}
              {locations.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {locations.map((loc, i) => (
                    <button
                      key={i}
                      onClick={() => onLocationClick && onLocationClick(0, 0)} // Would need coords
                      className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded hover:bg-blue-500/30 transition-colors"
                    >
                      📍 {loc}
                    </button>
                  ))}
                </div>
              )}

              {/* Media indicator */}
              {msg.media_url && (
                <div className="mt-2 text-xs text-gray-500">
                  📎 {msg.media_type === 'video' ? '🎥 Video' : '🖼️ Image'} attached
                </div>
              )}
            </div>
          );
        })}

        {loading && messages.length === 0 && (
          <div className="p-8 text-center">
            <div className="animate-spin text-4xl mb-4">📡</div>
            <p className="text-gray-400">Loading feed...</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-700 bg-gray-800/50 text-xs text-gray-500 text-center">
        {messages.length} messages from {channels.length} channels
      </div>
    </div>
  );
}

