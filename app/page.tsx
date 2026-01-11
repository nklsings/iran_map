"use client";

import React, { useEffect, useState } from 'react';
import Map from '../components/Map';
import Sidebar from '../components/Sidebar';
import { ProtestEvent, FeatureCollection, Stats } from '../lib/types';

type ViewMode = 'all' | 'verified' | 'ppu';

export default function Home() {
  const [events, setEvents] = useState<ProtestEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ProtestEvent | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('all');

  // Use relative URLs in production (Cloud Run/Vercel), absolute in local dev
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchData = () => {
    let eventUrl = `${API_URL}/api/events?hours=168`;
    
    if (viewMode === 'verified') {
      eventUrl += '&verified_only=true';
    } else if (viewMode === 'ppu') {
      eventUrl += '&event_type=police_presence';
    }
    
    // Fetch Events
    fetch(eventUrl)
      .then(res => res.json())
      .then((data: FeatureCollection) => {
        setEvents(data.features || []);
      })
      .catch(err => console.error("Failed to fetch events", err));

    // Fetch Stats
    fetch(`${API_URL}/api/stats?hours=168`)
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Failed to fetch stats", err));
  };

  useEffect(() => {
    fetchData();
  }, [viewMode]);

  return (
    <main className="relative w-screen h-screen bg-black overflow-hidden">
      <Map 
        events={events} 
        onEventClick={setSelectedEvent}
        showPPU={viewMode !== 'verified'}
      />
      
      {/* Sidebar acts as both the stats panel (when nothing selected) and detail view */}
      <Sidebar 
        event={selectedEvent} 
        onClose={() => setSelectedEvent(null)}
        stats={stats}
      />
      
      {/* Layer Toggles */}
      <div className="absolute bottom-20 md:bottom-8 left-1/2 -translate-x-1/2 flex flex-wrap gap-2 md:gap-3 z-10 w-full md:w-auto px-4 justify-center">
        <button 
          className={`bg-zinc-900/90 backdrop-blur border px-3 md:px-5 py-2 rounded-full uppercase text-[10px] md:text-xs font-bold tracking-widest transition-all whitespace-nowrap ${
            viewMode === 'all' 
              ? 'text-red-500 border-red-900/50 hover:bg-red-900/20 shadow-[0_0_15px_rgba(220,38,38,0.3)]' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={() => setViewMode('all')}
        >
          🔴 All Events
        </button>
        <button 
          className={`bg-zinc-900/90 backdrop-blur border px-3 md:px-5 py-2 rounded-full uppercase text-[10px] md:text-xs font-bold tracking-widest transition-all whitespace-nowrap ${
            viewMode === 'ppu' 
              ? 'text-blue-400 border-blue-900/50 hover:bg-blue-900/20 shadow-[0_0_15px_rgba(59,130,246,0.3)]' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={() => setViewMode('ppu')}
        >
          🚨 PPU Only
          {stats?.police_presence ? (
            <span className="ml-1 text-blue-300">({stats.police_presence})</span>
          ) : null}
        </button>
        <button 
          className={`bg-zinc-900/90 backdrop-blur border px-3 md:px-5 py-2 rounded-full uppercase text-[10px] md:text-xs font-bold tracking-widest transition-all whitespace-nowrap ${
            viewMode === 'verified' 
              ? 'text-white border-white/50 bg-white/10 shadow-[0_0_15px_rgba(255,255,255,0.2)]' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={() => setViewMode('verified')}
        >
          ✓ Verified
        </button>
      </div>
    </main>
  );
}
