"use client";

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Map from '../components/Map';
import Sidebar from '../components/Sidebar';
import { ProtestEvent, FeatureCollection, Stats, MEDIA_SOURCES, OSINT_SOURCES, OTHER_SOURCES, getEventSourceId, AirspaceEvent, AirspaceCollection, ProvinceConnectivity, ConnectivityCollection, CONNECTIVITY_STATUS_CONFIG } from '../lib/types';
import { RefreshCw, Filter, ChevronDown, ChevronUp } from 'lucide-react';

type ViewMode = 'all' | 'verified' | 'ppu';

// Auto-refresh interval in milliseconds (2 minutes)
const AUTO_REFRESH_INTERVAL = 2 * 60 * 1000;

export default function Home() {
  const [events, setEvents] = useState<ProtestEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ProtestEvent | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [showSourceFilter, setShowSourceFilter] = useState(false);
  const [showAirspace, setShowAirspace] = useState(true);
  const [airspaceData, setAirspaceData] = useState<AirspaceEvent[]>([]);
  const [showConnectivity, setShowConnectivity] = useState(false);
  const [connectivityData, setConnectivityData] = useState<ProvinceConnectivity[]>([]);
  const [nationalConnectivity, setNationalConnectivity] = useState<{score: number; status: string} | null>(null);
  const [selectedProvince, setSelectedProvince] = useState<ProvinceConnectivity | null>(null);
  const [enabledSources, setEnabledSources] = useState<Record<string, boolean>>(() => {
    // Initialize from source definitions
    const initial: Record<string, boolean> = {};
    [...MEDIA_SOURCES, ...OSINT_SOURCES, ...OTHER_SOURCES].forEach(s => {
      initial[s.id] = s.enabled;
    });
    return initial;
  });

  const toggleSource = (sourceId: string) => {
    setEnabledSources(prev => ({
      ...prev,
      [sourceId]: !prev[sourceId]
    }));
  };

  // Filter events based on enabled sources
  const filteredEvents = useMemo(() => {
    // If all sources are enabled, return all events (optimization)
    const allSources = [...MEDIA_SOURCES, ...OSINT_SOURCES, ...OTHER_SOURCES];
    const allEnabled = allSources.every(s => enabledSources[s.id] ?? s.enabled);
    if (allEnabled) return events;

    return events.filter(event => {
      const sourceId = getEventSourceId(event.properties.title, event.properties.source_url);
      // Show only if the source is enabled
      return enabledSources[sourceId] ?? false;
    });
  }, [events, enabledSources]);

  // Count of filtered vs total
  const filterCount = filteredEvents.length !== events.length 
    ? `${filteredEvents.length}/${events.length}` 
    : null;

  // Use relative URLs in production (Cloud Run/Vercel), absolute in local dev
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchData = useCallback(async (showSpinner = true) => {
    if (showSpinner) setIsRefreshing(true);
    
    let eventUrl = `${API_URL}/api/events?hours=12`;
    
    if (viewMode === 'verified') {
      eventUrl += '&verified_only=true';
    } else if (viewMode === 'ppu') {
      eventUrl += '&event_type=police_presence';
    }
    
    try {
      // Fetch Events, Stats, Airspace, and Connectivity in parallel
      // fetch_new=true will fetch real NOTAMs if the database is empty
      const [eventsRes, statsRes, airspaceRes, connectivityRes] = await Promise.all([
        fetch(eventUrl),
        fetch(`${API_URL}/api/stats?hours=12`),
        fetch(`${API_URL}/api/airspace?active_only=true&fetch_new=true`),
        fetch(`${API_URL}/api/connectivity`)
      ]);
      
      const eventsData: FeatureCollection = await eventsRes.json();
      const statsData = await statsRes.json();
      
      setEvents(eventsData.features || []);
      setStats(statsData);
      setLastRefresh(new Date());
      
      // Airspace data (may fail if not configured)
      try {
        const airspaceDataRes: AirspaceCollection = await airspaceRes.json();
        setAirspaceData(airspaceDataRes.features || []);
      } catch {
        // Airspace endpoint may not be available yet
        setAirspaceData([]);
      }
      
      // Connectivity data
      try {
        const connectivityDataRes: ConnectivityCollection = await connectivityRes.json();
        setConnectivityData(connectivityDataRes.features || []);
        if (connectivityDataRes.metadata) {
          setNationalConnectivity({
            score: connectivityDataRes.metadata.national_score,
            status: connectivityDataRes.metadata.national_status
          });
        }
      } catch {
        // Connectivity endpoint may not be available yet
        setConnectivityData([]);
      }
    } catch (err) {
      console.error("Failed to fetch data", err);
    } finally {
      setIsRefreshing(false);
    }
  }, [viewMode, API_URL]);

  // Initial fetch and when viewMode changes
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh interval
  useEffect(() => {
    if (!autoRefreshEnabled) return;
    
    const interval = setInterval(() => {
      fetchData(false); // Don't show spinner for auto-refresh
    }, AUTO_REFRESH_INTERVAL);
    
    return () => clearInterval(interval);
  }, [autoRefreshEnabled, fetchData]);

  // Format last refresh time
  const getRefreshText = () => {
    if (!lastRefresh) return '';
    const seconds = Math.floor((Date.now() - lastRefresh.getTime()) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ago`;
  };

  return (
    <main className="relative w-screen h-screen bg-black overflow-hidden">
      <Map 
        events={filteredEvents} 
        onEventClick={setSelectedEvent}
        showPPU={viewMode !== 'verified'}
        airspaceData={airspaceData}
        showAirspace={showAirspace}
        connectivityData={connectivityData}
        showConnectivity={showConnectivity}
        onConnectivityClick={setSelectedProvince}
      />
      
      {/* Sidebar acts as both the stats panel (when nothing selected) and detail view */}
      <Sidebar 
        event={selectedEvent} 
        onClose={() => setSelectedEvent(null)}
        stats={stats}
      />
      
      {/* Refresh Button - Top Right */}
      <div className="absolute top-4 right-4 md:right-[420px] z-20 flex items-center gap-2">
        <button
          onClick={() => fetchData(true)}
          disabled={isRefreshing}
          className={`flex items-center gap-2 bg-zinc-900/90 backdrop-blur border border-zinc-700 px-3 py-2 rounded-lg text-xs font-medium transition-all hover:bg-zinc-800 ${
            isRefreshing ? 'text-gray-500' : 'text-white'
          }`}
          title="Refresh data"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span className="hidden md:inline">
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </span>
        </button>
        
        {/* Auto-refresh toggle */}
        <button
          onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
          className={`flex items-center gap-1.5 bg-zinc-900/90 backdrop-blur border px-3 py-2 rounded-lg text-xs font-medium transition-all ${
            autoRefreshEnabled 
              ? 'border-green-700 text-green-400 hover:bg-green-900/20' 
              : 'border-zinc-700 text-gray-500 hover:text-white hover:bg-zinc-800'
          }`}
          title={autoRefreshEnabled ? 'Auto-refresh ON (2min)' : 'Auto-refresh OFF'}
        >
          <span className={`w-2 h-2 rounded-full ${autoRefreshEnabled ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`} />
          <span className="hidden md:inline">Auto</span>
        </button>
        
        {/* Last refresh time */}
        {lastRefresh && (
          <span className="hidden md:block text-xs text-gray-500">
            {getRefreshText()}
          </span>
        )}
      </div>

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
        <button 
          className={`bg-zinc-900/90 backdrop-blur border px-3 md:px-5 py-2 rounded-full uppercase text-[10px] md:text-xs font-bold tracking-widest transition-all whitespace-nowrap ${
            showAirspace 
              ? 'text-cyan-400 border-cyan-900/50 hover:bg-cyan-900/20 shadow-[0_0_15px_rgba(6,182,212,0.3)]' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={() => setShowAirspace(!showAirspace)}
          title="Toggle NOTAM airspace restrictions"
        >
          ✈️ NOTAMs
          {airspaceData.length > 0 && (
            <span className="ml-1 text-cyan-300">({airspaceData.length})</span>
          )}
        </button>
        <button 
          className={`bg-zinc-900/90 backdrop-blur border px-3 md:px-5 py-2 rounded-full uppercase text-[10px] md:text-xs font-bold tracking-widest transition-all whitespace-nowrap ${
            showConnectivity 
              ? 'text-green-400 border-green-900/50 hover:bg-green-900/20 shadow-[0_0_15px_rgba(34,197,94,0.3)]' 
              : 'text-gray-500 border-gray-800 hover:text-white'
          }`}
          onClick={() => setShowConnectivity(!showConnectivity)}
          title="Toggle internet connectivity layer"
        >
          📶 Internet
          {nationalConnectivity && (
            <span className={`ml-1 ${
              nationalConnectivity.status === 'normal' ? 'text-green-300' :
              nationalConnectivity.status === 'degraded' ? 'text-yellow-300' :
              nationalConnectivity.status === 'restricted' ? 'text-orange-300' :
              nationalConnectivity.status === 'blackout' ? 'text-red-300' : 'text-gray-300'
            }`}>
              ({Math.round(nationalConnectivity.score * 100)}%)
            </span>
          )}
        </button>
        <a 
          href="/summary"
          className="bg-zinc-900/90 backdrop-blur border border-amber-800/50 px-3 md:px-5 py-2 rounded-full uppercase text-[10px] md:text-xs font-bold tracking-widest transition-all whitespace-nowrap text-amber-400 hover:bg-amber-900/20 hover:shadow-[0_0_15px_rgba(245,158,11,0.3)]"
          title="View AI-generated situation summary"
        >
          📊 Summary
        </a>
      </div>
      
      {/* Connectivity Province Info Popup */}
      {selectedProvince && showConnectivity && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-30 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-xl p-4 shadow-xl max-w-sm">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-white">{selectedProvince.properties.name}</h3>
            <button 
              onClick={() => setSelectedProvince(null)}
              className="text-zinc-400 hover:text-white text-lg"
            >×</button>
          </div>
          <p className="text-zinc-400 text-sm mb-2">{selectedProvince.properties.name_fa}</p>
          <div className="flex items-center gap-2 mb-2">
            <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${
              selectedProvince.properties.status === 'normal' ? 'bg-green-500/20 text-green-400' :
              selectedProvince.properties.status === 'degraded' ? 'bg-yellow-500/20 text-yellow-400' :
              selectedProvince.properties.status === 'restricted' ? 'bg-orange-500/20 text-orange-400' :
              selectedProvince.properties.status === 'blackout' ? 'bg-red-500/20 text-red-400' :
              'bg-gray-500/20 text-gray-400'
            }`}>
              {CONNECTIVITY_STATUS_CONFIG[selectedProvince.properties.status]?.icon} {selectedProvince.properties.status}
            </span>
            <span className="text-white font-bold">
              {Math.round(selectedProvince.properties.connectivity_score * 100)}%
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            {CONNECTIVITY_STATUS_CONFIG[selectedProvince.properties.status]?.description}
          </p>
          <p className="text-xs text-zinc-600 mt-2">
            Pop: {(selectedProvince.properties.population / 1000000).toFixed(1)}M
          </p>
        </div>
      )}

      {/* Source Filter Panel */}
      <div className="absolute bottom-32 md:bottom-20 left-4 z-10">
        <button
          onClick={() => setShowSourceFilter(!showSourceFilter)}
          className={`flex items-center gap-2 bg-zinc-900/90 backdrop-blur border px-3 py-2 rounded-lg text-xs font-medium transition-all hover:bg-zinc-800 ${
            filterCount ? 'border-amber-600 text-amber-400' : 'border-zinc-700 text-white'
          }`}
        >
          <Filter className="w-4 h-4" />
          <span className="hidden md:inline">Sources</span>
          {filterCount && (
            <span className="bg-amber-600/20 text-amber-400 px-1.5 py-0.5 rounded text-[10px] font-bold">
              {filterCount}
            </span>
          )}
          {showSourceFilter ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
        </button>
        
        {showSourceFilter && (
          <div className="mt-2 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-lg p-3 max-h-[60vh] overflow-y-auto w-64 md:w-72 shadow-xl">
            {/* Media Sources */}
            <div className="mb-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                📺 Media / Channels
              </h3>
              <div className="space-y-1.5">
                {MEDIA_SOURCES.map((source) => (
                  <label
                    key={source.id}
                    className="flex items-center gap-2 text-xs cursor-pointer hover:bg-zinc-800/50 p-1.5 rounded transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={enabledSources[source.id] ?? source.enabled}
                      onChange={() => toggleSource(source.id)}
                      className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-red-500 focus:ring-red-500 focus:ring-offset-0"
                    />
                    <span className={enabledSources[source.id] ? 'text-white' : 'text-gray-500'}>
                      {source.name}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* OSINT / Verification / Safety Sources */}
            <div className="mb-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                🔍 OSINT / Verification / Safety
              </h3>
              <div className="space-y-1.5">
                {OSINT_SOURCES.map((source) => (
                  <label
                    key={source.id}
                    className={`flex items-center gap-2 text-xs cursor-pointer p-1.5 rounded transition-colors ${
                      source.enabled ? 'hover:bg-zinc-800/50' : 'opacity-50 cursor-not-allowed'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={enabledSources[source.id] ?? source.enabled}
                      onChange={() => source.enabled && toggleSource(source.id)}
                      disabled={!source.enabled}
                      className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0 disabled:opacity-50"
                    />
                    <span className={enabledSources[source.id] && source.enabled ? 'text-white' : 'text-gray-500'}>
                      {source.icon && <span className="mr-1">{source.icon}</span>}
                      {source.name}
                      {source.category === 'verification' && (
                        <span className="ml-1 text-[10px] text-emerald-400">(verification)</span>
                      )}
                      {source.category === 'safety' && (
                        <span className="ml-1 text-[10px] text-amber-400">(safety)</span>
                      )}
                      {!source.enabled && (
                        <span className="ml-1 text-[10px] text-gray-600">(disabled)</span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Other Sources (platforms) */}
            <div>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                📡 Other Sources
              </h3>
              <div className="space-y-1.5">
                {OTHER_SOURCES.map((source) => (
                  <label
                    key={source.id}
                    className="flex items-center gap-2 text-xs cursor-pointer hover:bg-zinc-800/50 p-1.5 rounded transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={enabledSources[source.id] ?? source.enabled}
                      onChange={() => toggleSource(source.id)}
                      className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-purple-500 focus:ring-purple-500 focus:ring-offset-0"
                    />
                    <span className={enabledSources[source.id] ? 'text-white' : 'text-gray-500'}>
                      {source.icon && <span className="mr-1">{source.icon}</span>}
                      {source.name}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-zinc-800 text-[10px] text-gray-500">
              {filterCount ? (
                <span className="text-amber-400">Showing {filterCount} events</span>
              ) : (
                <span>Toggle sources to filter events on the map</span>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
