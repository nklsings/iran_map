'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  Shield,
  ShieldAlert,
  Clock,
  Share2,
  Languages,
  ExternalLink,
  Loader2,
  AlertTriangle,
  Siren,
} from 'lucide-react';
import { ProtestEvent, Stats, EventType } from '../lib/types';
import { format } from 'date-fns';

// Event type display configuration
const EVENT_TYPE_CONFIG: Record<
  EventType,
  { label: string; emoji: string; color: string; bgColor: string }
> = {
  protest: {
    label: 'Protest',
    emoji: '✊',
    color: 'text-red-400',
    bgColor: 'bg-red-600',
  },
  police_presence: {
    label: 'Police Presence',
    emoji: '🚨',
    color: 'text-blue-400',
    bgColor: 'bg-blue-600',
  },
  clash: {
    label: 'Clash',
    emoji: '⚡',
    color: 'text-orange-400',
    bgColor: 'bg-orange-600',
  },
  arrest: {
    label: 'Arrest',
    emoji: '🔒',
    color: 'text-purple-400',
    bgColor: 'bg-purple-600',
  },
  strike: {
    label: 'Strike',
    emoji: '🛑',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-600',
  },
};

interface ClusterEvent {
  id: number;
  title: string;
  description: string;
  timestamp: string | null;
  event_type: EventType;
  verified: boolean;
  source_url: string | null;
}

interface SidebarProps {
  event: ProtestEvent | null;
  onClose: () => void;
  stats: Stats | null;
  allEvents?: ProtestEvent[]; // All events for looking up cluster contents
}

export default function Sidebar({
  event,
  onClose,
  stats,
  allEvents = [],
}: SidebarProps) {
  const [translatedTitle, setTranslatedTitle] = useState<string | null>(null);
  const [translatedDesc, setTranslatedDesc] = useState<string | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);
  const [clusterEvents, setClusterEvents] = useState<ClusterEvent[]>([]);
  const [loadingCluster, setLoadingCluster] = useState(false);

  // Use relative URLs in production (Cloud Run/Vercel), absolute in local dev
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // Reset translation state and fetch cluster events when event changes
  useEffect(() => {
    setTranslatedTitle(null);
    setTranslatedDesc(null);
    setShowTranslation(false);
    setClusterEvents([]);

    // If this is a cluster, fetch the individual events
    if (event?.properties.is_cluster && event.properties.event_ids) {
      fetchClusterEvents(event.properties.event_ids);
    }
  }, [event?.properties.id]);

  const fetchClusterEvents = async (eventIds: number[]) => {
    setLoadingCluster(true);
    try {
      // Fetch unclustered events to get individual details
      const response = await fetch(
        `${API_URL}/api/events?hours=12&cluster=false`
      );
      const data = await response.json();

      // Filter to only the events in this cluster
      const clusterData = data.features
        .filter((e: ProtestEvent) =>
          eventIds.includes(e.properties.id as number)
        )
        .map((e: ProtestEvent) => ({
          id: e.properties.id as number,
          title: e.properties.title,
          description: e.properties.description,
          timestamp: e.properties.timestamp,
          event_type: e.properties.event_type,
          verified: e.properties.verified,
          source_url: e.properties.source_url,
        }));

      setClusterEvents(clusterData);
    } catch (error) {
      console.error('Failed to fetch cluster events:', error);
    } finally {
      setLoadingCluster(false);
    }
  };

  const handleTranslate = async () => {
    if (!event) return;

    if (showTranslation && translatedTitle) {
      // Toggle off
      setShowTranslation(false);
      return;
    }

    setIsTranslating(true);
    try {
      // Translate title
      const titleRes = await fetch(`${API_URL}/api/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: event.properties.title }),
      });
      const titleData = await titleRes.json();
      setTranslatedTitle(titleData.translated);

      // Translate description
      if (event.properties.description) {
        const descRes = await fetch(`${API_URL}/api/translate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: event.properties.description }),
        });
        const descData = await descRes.json();
        setTranslatedDesc(descData.translated);
      }

      setShowTranslation(true);
    } catch (err) {
      console.error('Translation failed:', err);
    } finally {
      setIsTranslating(false);
    }
  };

  const handleShare = async () => {
    if (!event) return;

    const shareData = {
      title: 'Iran Protest Report',
      text: `${event.properties.title} - Reported at ${event.properties.timestamp}`,
      url: window.location.href,
    };

    if (navigator.share) {
      try {
        await navigator.share(shareData);
      } catch (err) {
        // User cancelled or error
        console.log('Share cancelled');
      }
    } else {
      // Fallback: copy to clipboard
      const shareText = `${shareData.title}\n${shareData.text}\n${shareData.url}`;
      await navigator.clipboard.writeText(shareText);
      alert('Link copied to clipboard');
    }
  };

  const handleViewSource = () => {
    if (event?.properties.source_url) {
      window.open(event.properties.source_url, '_blank', 'noopener,noreferrer');
    }
  };

  if (!event) {
    return (
      <div className="absolute top-4 left-4 right-4 md:right-auto md:w-80 z-10 bg-black/90 text-white p-4 md:p-6 border-l-4 border-red-600 backdrop-blur-md rounded-br-lg shadow-2xl">
        <h1 className="text-xl md:text-2xl font-bold tracking-tighter mb-2 text-red-500 uppercase flex justify-between items-center">
          <span>Iran Protest Map</span>
          <div className="flex md:hidden gap-2">
            {/* Mobile stats summary */}
            <span className="text-white text-sm font-mono">
              {stats?.total_reports || 0} Reports
            </span>
          </div>
        </h1>

        {/* Desktop full stats */}
        <div className="hidden md:block space-y-3">
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm">Total Reports</span>
            <span className="text-xl font-mono text-red-500">
              {stats?.total_reports || 0}
            </span>
          </div>
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm flex items-center gap-1">
              <Siren size={14} className="text-blue-400" /> PPU Alerts
            </span>
            <span className="text-xl font-mono text-blue-400">
              {stats?.police_presence || 0}
            </span>
          </div>
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm">Verified</span>
            <span className="text-xl font-mono text-white">
              {stats?.verified_incidents || 0}
            </span>
          </div>

          {/* Event type breakdown */}
          <div className="grid grid-cols-2 gap-2 text-xs mt-3">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              <span className="text-gray-500">Protests:</span>
              <span className="text-gray-300 ml-auto">
                {stats?.protests || 0}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-orange-500"></span>
              <span className="text-gray-500">Clashes:</span>
              <span className="text-gray-300 ml-auto">
                {stats?.clashes || 0}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-purple-500"></span>
              <span className="text-gray-500">Arrests:</span>
              <span className="text-gray-300 ml-auto">
                {stats?.arrests || 0}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              <span className="text-gray-500">Police:</span>
              <span className="text-gray-300 ml-auto">
                {stats?.police_presence || 0}
              </span>
            </div>
          </div>

          <p className="text-xs text-gray-500 mt-3">
            🔴 Red = Protest • 🔵 Blue = Police (PPU) • ⚪ White = Verified
          </p>
        </div>

        {/* Mobile simplified hint */}
        <div className="md:hidden text-xs text-gray-500 mt-1">
          🔴 Protest • 🔵 Police (PPU) • ⚪ Verified. Tap for details.
        </div>
      </div>
    );
  }

  const displayTitle =
    showTranslation && translatedTitle
      ? translatedTitle
      : event.properties.title;
  const displayDesc =
    showTranslation && translatedDesc
      ? translatedDesc
      : event.properties.description;

  // Determine border color based on event type
  const eventType = event.properties.event_type || 'protest';
  const borderColorClass =
    eventType === 'police_presence'
      ? 'border-blue-600'
      : eventType === 'clash'
      ? 'border-orange-600'
      : eventType === 'arrest'
      ? 'border-purple-600'
      : 'border-red-600';

  return (
    <div
      className={`absolute inset-x-0 bottom-0 md:top-4 md:bottom-auto md:right-4 md:left-auto md:w-96 z-20 bg-zinc-950 text-white border-t-4 md:border-t-0 md:border-r-4 ${borderColorClass} shadow-2xl max-h-[80vh] md:h-[calc(100vh-2rem)] overflow-y-auto rounded-t-xl md:rounded-xl md:rounded-r-none transition-transform duration-300 ease-in-out`}>
      <div className="p-4 md:p-6">
        {/* Close button - adjusted for mobile hit area */}
        <button
          onClick={onClose}
          className="absolute top-2 right-2 md:top-4 md:right-4 p-2 text-gray-400 hover:text-white bg-black/20 rounded-full md:bg-transparent">
          <X size={24} />
        </button>

        <div className="flex items-center gap-2 mb-4 flex-wrap pr-8 md:pr-0">
          {/* Cluster badge - show first if it's a cluster */}
          {event.properties.is_cluster && (
            <span className="flex items-center gap-1 bg-linear-to-r from-amber-500 to-orange-500 text-black px-2 py-0.5 text-xs font-bold uppercase tracking-wider">
              📍 {event.properties.cluster_count} Reports
            </span>
          )}

          {/* Event type badge */}
          {(() => {
            const eventType = event.properties.event_type || 'protest';
            const config =
              EVENT_TYPE_CONFIG[eventType] || EVENT_TYPE_CONFIG.protest;
            return (
              <span
                className={`flex items-center gap-1 ${config.bgColor} text-white px-2 py-0.5 text-xs font-bold uppercase tracking-wider`}>
                {config.emoji} {config.label}
              </span>
            );
          })()}

          {/* Verified badge */}
          {event.properties.verified ? (
            <span className="flex items-center gap-1 bg-white text-black px-2 py-0.5 text-xs font-bold uppercase tracking-wider">
              <Shield size={12} /> Verified
            </span>
          ) : (
            <span className="flex items-center gap-1 bg-zinc-700 text-gray-300 px-2 py-0.5 text-xs font-medium uppercase tracking-wider">
              <ShieldAlert size={12} /> Unverified
            </span>
          )}

          {!event.properties.is_cluster && (
            <span className="text-gray-500 text-xs font-mono">
              ID: {event.properties.id}
            </span>
          )}

          {/* Translate button - only show for non-clusters */}
          {!event.properties.is_cluster && (
            <button
              onClick={handleTranslate}
              disabled={isTranslating}
              className={`ml-auto flex items-center gap-1 px-2 py-0.5 text-xs font-medium transition-colors ${
                showTranslation
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-800 text-gray-300 hover:bg-zinc-700'
              }`}>
              {isTranslating ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Languages size={12} />
              )}
              {showTranslation ? 'Original' : 'Translate'}
            </button>
          )}
        </div>

        {/* Cluster breakdown */}
        {event.properties.is_cluster && event.properties.type_breakdown && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 mb-4">
            <div className="text-xs text-gray-400 uppercase tracking-wider mb-2">
              Event Types in Cluster
            </div>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(event.properties.type_breakdown).map(
                ([type, count]) => {
                  const config =
                    EVENT_TYPE_CONFIG[type as EventType] ||
                    EVENT_TYPE_CONFIG.protest;
                  return (
                    <div key={type} className="flex items-center gap-2">
                      <span
                        className={`w-3 h-3 rounded-full ${config.bgColor}`}></span>
                      <span className="text-gray-300 text-sm capitalize">
                        {type.replace('_', ' ')}
                      </span>
                      <span className="text-white font-mono ml-auto">
                        {count as number}
                      </span>
                    </div>
                  );
                }
              )}
            </div>
          </div>
        )}

        {/* Show individual events in cluster */}
        {event.properties.is_cluster && (
          <div className="mb-6">
            <div className="text-xs text-gray-400 uppercase tracking-wider mb-3">
              Reports in this area ({event.properties.cluster_count})
            </div>

            {loadingCluster ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
              </div>
            ) : clusterEvents.length > 0 ? (
              <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-2">
                {clusterEvents.map((ce) => {
                  const config =
                    EVENT_TYPE_CONFIG[ce.event_type] ||
                    EVENT_TYPE_CONFIG.protest;
                  return (
                    <div
                      key={ce.id}
                      className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 hover:border-zinc-700 transition-colors">
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className={`${config.bgColor} text-white px-1.5 py-0.5 text-xs font-bold rounded`}>
                          {config.emoji}
                        </span>
                        {ce.verified && (
                          <span className="bg-white text-black px-1.5 py-0.5 text-xs font-bold rounded flex items-center gap-1">
                            <Shield size={10} /> Verified
                          </span>
                        )}
                        <span className="text-gray-500 text-xs ml-auto">
                          #{ce.id}
                        </span>
                      </div>
                      <h4
                        className="text-sm font-medium text-white mb-1"
                        dir="rtl">
                        {ce.title}
                      </h4>
                      {ce.description && (
                        <p
                          className="text-xs text-gray-400 line-clamp-2"
                          dir="rtl">
                          {ce.description}
                        </p>
                      )}
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-xs text-gray-500">
                          {ce.timestamp
                            ? format(new Date(ce.timestamp), 'MMM d, HH:mm')
                            : 'Unknown'}
                        </span>
                        {ce.source_url && (
                          <a
                            href={ce.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
                            Source <ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">Loading reports...</p>
            )}
          </div>
        )}

        {/* Single event display */}
        {!event.properties.is_cluster && (
          <>
            <h2
              className="text-xl font-bold mb-4"
              dir={showTranslation ? 'ltr' : 'rtl'}>
              {displayTitle}
            </h2>

            <div className="flex items-center gap-2 text-gray-400 text-sm mb-6">
              <Clock size={16} />
              {event.properties.timestamp
                ? format(
                    new Date(event.properties.timestamp),
                    'MMM d, yyyy HH:mm'
                  )
                : 'Unknown Time'}
            </div>

            <div className="prose prose-invert prose-sm mb-6">
              <p dir={showTranslation ? 'ltr' : 'rtl'}>{displayDesc}</p>
            </div>
          </>
        )}

        {/* Media display */}
        {event.properties.media_url ? (
          <div className="mb-6">
            {event.properties.media_type === 'video' ? (
              // Actual video - can be played
              <div className="relative aspect-video bg-zinc-900 border border-zinc-800 overflow-hidden rounded">
                <video
                  src={event.properties.media_url}
                  controls
                  className="w-full h-full object-contain"
                  poster=""
                  preload="metadata">
                  Your browser does not support video playback.
                </video>
              </div>
            ) : event.properties.media_type === 'video_thumb' ? (
              // Video thumbnail only - link to source
              <a
                href={event.properties.source_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="block relative aspect-video bg-zinc-900 border border-zinc-800 overflow-hidden rounded group">
                <img
                  src={event.properties.media_url}
                  alt="Video thumbnail"
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 group-hover:bg-black/60 transition-colors">
                  <div className="w-16 h-16 rounded-full bg-red-600/90 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <svg
                      className="w-8 h-8 text-white ml-1"
                      fill="currentColor"
                      viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </div>
                </div>
                <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white">
                  View on Telegram
                </div>
              </a>
            ) : (
              // Image
              <a
                href={event.properties.source_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="block">
                <img
                  src={event.properties.media_url}
                  alt="Media from report"
                  className="w-full rounded border border-zinc-800 hover:border-red-600 transition-colors"
                  loading="lazy"
                />
              </a>
            )}
            <div className="text-xs text-gray-500 mt-2 flex items-center gap-1">
              {event.properties.media_type === 'video'
                ? '🎥 Video (playable)'
                : event.properties.media_type === 'video_thumb'
                ? '🎥 Video (click to view)'
                : '📷 Image'}{' '}
              from Telegram
            </div>
          </div>
        ) : (
          <div className="aspect-video bg-zinc-900/50 flex items-center justify-center mb-6 border border-zinc-800/50 rounded">
            <span className="text-zinc-600 text-sm">No media attached</span>
          </div>
        )}

        {/* Source info */}
        {event.properties.source_url && (
          <div className="text-xs text-gray-500 mb-4 truncate">
            Source:{' '}
            {(() => {
              try {
                return new URL(event.properties.source_url).hostname;
              } catch {
                return 'Unknown';
              }
            })()}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleViewSource}
            disabled={!event.properties.source_url}
            className={`flex-1 flex items-center justify-center gap-2 py-2 font-medium transition-colors text-sm uppercase tracking-wide ${
              event.properties.source_url
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
            }`}>
            <ExternalLink size={16} />
            View Source
          </button>
          <button
            onClick={handleShare}
            className="p-2 border border-zinc-700 hover:bg-zinc-800 transition-colors"
            title="Share this report">
            <Share2 size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
