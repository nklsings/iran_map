import React from 'react';
import { X, Shield, ShieldAlert, Clock, Share2 } from 'lucide-react';
import { ProtestEvent } from '../lib/types';
import { format } from 'date-fns';

interface SidebarProps {
  event: ProtestEvent | null;
  onClose: () => void;
  stats: any;
}

export default function Sidebar({ event, onClose, stats }: SidebarProps) {
  if (!event) {
    return (
      <div className="absolute top-4 left-4 z-10 w-80 bg-black/90 text-white p-6 border-l-4 border-red-600 backdrop-blur-md rounded-br-lg shadow-2xl">
        <h1 className="text-2xl font-bold tracking-tighter mb-2 text-red-500 uppercase">Iran Protest Map</h1>
        <div className="space-y-4">
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm">Active Reports</span>
            <span className="text-xl font-mono text-red-500">{stats?.total_reports || 0}</span>
          </div>
          <div className="flex justify-between items-center border-b border-gray-800 pb-2">
            <span className="text-gray-400 text-sm">Verified Incidents</span>
            <span className="text-xl font-mono text-white">{stats?.verified_incidents || 0}</span>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            Live intelligence map. Red indicates unverified reports. White indicates verified incidents.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute top-4 right-4 z-10 w-96 bg-zinc-950 text-white border-r-4 border-red-600 shadow-2xl h-[calc(100vh-2rem)] overflow-y-auto">
      <div className="p-6">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white"
        >
          <X size={24} />
        </button>

        <div className="flex items-center gap-2 mb-4">
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
        </div>

        <h2 className="text-xl font-bold mb-4">{event.properties.title}</h2>
        
        <div className="flex items-center gap-2 text-gray-400 text-sm mb-6">
          <Clock size={16} />
          {event.properties.timestamp ? format(new Date(event.properties.timestamp), 'MMM d, yyyy HH:mm') : 'Unknown Time'}
        </div>

        <div className="prose prose-invert prose-sm mb-8">
          <p>{event.properties.description}</p>
        </div>

        {/* Placeholder for media */}
        <div className="aspect-video bg-zinc-900 flex items-center justify-center mb-6 border border-zinc-800">
          <span className="text-zinc-700 text-sm">No media attached</span>
        </div>

        <div className="flex gap-2">
          <button className="flex-1 bg-red-600 hover:bg-red-700 text-white py-2 font-medium transition-colors text-sm uppercase tracking-wide">
            View Source
          </button>
          <button className="p-2 border border-zinc-700 hover:bg-zinc-800 transition-colors">
            <Share2 size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}

