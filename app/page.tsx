"use client";

import React, { useEffect, useState } from 'react';
import Map from '../components/Map';
import Sidebar from '../components/Sidebar';
import { ProtestEvent, FeatureCollection } from '../lib/types';

export default function Home() {
  const [events, setEvents] = useState<ProtestEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ProtestEvent | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  // Use relative URLs in production (Cloud Run/Vercel), absolute in local dev
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchData = (verified: boolean) => {
    const verifiedParam = verified ? '&verified_only=true' : '';
    
    // Fetch Events
    fetch(`${API_URL}/api/events?hours=168${verifiedParam}`)
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
    fetchData(verifiedOnly);
  }, [verifiedOnly]);

  const handleVerifiedToggle = () => {
    setVerifiedOnly(!verifiedOnly);
  };

  return (
    <main className="relative w-screen h-screen bg-black overflow-hidden">
      <Map 
        events={events} 
        onEventClick={setSelectedEvent}
      />
      
      {/* Sidebar acts as both the stats panel (when nothing selected) and detail view */}
      <Sidebar 
        event={selectedEvent} 
        onClose={() => setSelectedEvent(null)}
        stats={stats}
      />
      
      {/* Narrative/Layer Toggles */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-4 z-10">
        <button 
          className={`bg-zinc-900/80 backdrop-blur border px-6 py-2 rounded-full uppercase text-xs font-bold tracking-widest transition-all ${
            !verifiedOnly 
              ? 'text-red-500 border-red-900/50 hover:bg-red-900/20' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={() => setVerifiedOnly(false)}
        >
          Live Heatmap
        </button>
        <button 
          className={`bg-zinc-900/80 backdrop-blur border px-6 py-2 rounded-full uppercase text-xs font-bold tracking-widest transition-all ${
            verifiedOnly 
              ? 'text-white border-white/50 bg-white/10' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={handleVerifiedToggle}
        >
          Verified Only
        </button>
      </div>
    </main>
  );
}
