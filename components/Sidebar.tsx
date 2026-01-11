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
} from 'lucide-react';
import { ProtestEvent } from '../lib/types';
import { format } from 'date-fns';

interface SidebarProps {
  event: ProtestEvent | null;
  onClose: () => void;
  stats: any;
}

export default function Sidebar({ event, onClose, stats }: SidebarProps) {
  const [translatedTitle, setTranslatedTitle] = useState<string | null>(null);
  const [translatedDesc, setTranslatedDesc] = useState<string | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);

  // Use relative URLs in production (Cloud Run/Vercel), absolute in local dev
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // Reset translation state when event changes
  useEffect(() => {
    setTranslatedTitle(null);
    setTranslatedDesc(null);
    setShowTranslation(false);
  }, [event?.properties.id]);

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

        {/* Desktop full stats / Mobile expanded details could go here, but keeping it simple for now */}
        <div className="hidden md:block space-y-4">
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm">Reports (12h)</span>
            <span className="text-xl font-mono text-red-500">
              {stats?.total_reports || 0}
            </span>
          </div>
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm">Verified</span>
            <span className="text-xl font-mono text-white">
              {stats?.verified_incidents || 0}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            Live intelligence map. Red = unverified. White = verified. Click any
            point for details.
          </p>
        </div>

        {/* Mobile simplified hint */}
        <div className="md:hidden text-xs text-gray-500 mt-1">
          Tap points for details. Red: Unverified, White: Verified.
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

  return (
    <div className="absolute inset-x-0 bottom-0 md:top-4 md:bottom-auto md:right-4 md:left-auto md:w-96 z-20 bg-zinc-950 text-white border-t-4 md:border-t-0 md:border-r-4 border-red-600 shadow-2xl max-h-[80vh] md:h-[calc(100vh-2rem)] overflow-y-auto rounded-t-xl md:rounded-xl md:rounded-r-none transition-transform duration-300 ease-in-out">
      <div className="p-4 md:p-6">
        {/* Close button - adjusted for mobile hit area */}
        <button
          onClick={onClose}
          className="absolute top-2 right-2 md:top-4 md:right-4 p-2 text-gray-400 hover:text-white bg-black/20 rounded-full md:bg-transparent">
          <X size={24} />
        </button>

        <div className="flex items-center gap-2 mb-4 flex-wrap pr-8 md:pr-0">
          {event.properties.verified ? (
            <span className="flex items-center gap-1 bg-white text-black px-2 py-0.5 text-xs font-bold uppercase tracking-wider">
              <Shield size={12} /> Verified
            </span>
          ) : (
            <span className="flex items-center gap-1 bg-red-600 text-white px-2 py-0.5 text-xs font-bold uppercase tracking-wider">
              <ShieldAlert size={12} /> Unverified
            </span>
          )}
          <span className="text-gray-500 text-xs font-mono">
            ID: {event.properties.id}
          </span>

          {/* Translate button */}
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
        </div>

        <h2
          className="text-xl font-bold mb-4"
          dir={showTranslation ? 'ltr' : 'rtl'}>
          {displayTitle}
        </h2>

        <div className="flex items-center gap-2 text-gray-400 text-sm mb-6">
          <Clock size={16} />
          {event.properties.timestamp
            ? format(new Date(event.properties.timestamp), 'MMM d, yyyy HH:mm')
            : 'Unknown Time'}
        </div>

        <div className="prose prose-invert prose-sm mb-6">
          <p dir={showTranslation ? 'ltr' : 'rtl'}>{displayDesc}</p>
        </div>

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
