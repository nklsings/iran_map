"use client";

import React, { useEffect, useState } from 'react';
import Map from '../components/Map';
import Sidebar from '../components/Sidebar';
import { ProtestEvent, FeatureCollection } from '../lib/types';

export default function Home() {
  const [events, setEvents] = useState<ProtestEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ProtestEvent | null>(null);
  const [stats, setStats] = useState<any>(null);

  // Use relative URLs in production (Vercel), absolute in local dev
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    // Fetch Events
    fetch(`${API_URL}/api/events`)
      .then(res => res.json())
      .then((data: FeatureCollection) => {
        setEvents(data.features);
      })
      .catch(err => console.error("Failed to fetch events", err));

    // Fetch Stats
    fetch(`${API_URL}/api/stats`)
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Failed to fetch stats", err));
  }, [API_URL]);

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
      
      {/* Narrative/Layer Toggles (Simple Implementation) */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-4 z-10">
        <button className="bg-zinc-900/80 backdrop-blur text-red-500 border border-red-900/50 px-6 py-2 rounded-full uppercase text-xs font-bold tracking-widest hover:bg-red-900/20 transition-all">
          Live Heatmap
        </button>
        <button className="bg-zinc-900/80 backdrop-blur text-gray-500 border border-gray-800 px-6 py-2 rounded-full uppercase text-xs font-bold tracking-widest hover:text-white transition-all">
          Verified Only
        </button>
      </div>
    </main>
  );
}
