"use client";

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Map, { MapStyleName, MAP_STYLES } from '../components/Map';
import Sidebar from '../components/Sidebar';
import TelegramFeed from '../components/TelegramFeed';
import { ProtestEvent, FeatureCollection, Stats, MEDIA_SOURCES, OSINT_SOURCES, OTHER_SOURCES, getEventSourceId, AirspaceEvent, AirspaceCollection, ProvinceConnectivity, ConnectivityCollection, CONNECTIVITY_STATUS_CONFIG } from '../lib/types';
import { RefreshCw, Filter, ChevronDown, ChevronUp, Radio, BarChart3, Map as MapIcon, Menu, X, Layers, Shield, Globe, Loader2 } from 'lucide-react';

type ViewMode = 'all' | 'verified' | 'ppu';

// Auto-refresh interval in milliseconds (2 minutes)
const AUTO_REFRESH_INTERVAL = 2 * 60 * 1000;

export default function Home() {
  const [events, setEvents] = useState<ProtestEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ProtestEvent | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [showSourceFilter, setShowSourceFilter] = useState(false);
  const [showAirspace, setShowAirspace] = useState(true);
  const [airspaceData, setAirspaceData] = useState<AirspaceEvent[]>([]);
  const [showConnectivity, setShowConnectivity] = useState(false);
  const [connectivityData, setConnectivityData] = useState<ProvinceConnectivity[]>([]);
  const [nationalConnectivity, setNationalConnectivity] = useState<{score: number; status: string} | null>(null);
  const [selectedProvince, setSelectedProvince] = useState<ProvinceConnectivity | null>(null);
  const [showTelegramFeed, setShowTelegramFeed] = useState(false);
  const [mapStyle, setMapStyle] = useState<MapStyleName>('dark');
  const [showMapStylePicker, setShowMapStylePicker] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
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
    
    let eventUrl = `${API_URL}/api/events?hours=24`; // Last 24 hours
    
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
        fetch(`${API_URL}/api/stats?hours=24`),
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
      setIsInitialLoad(false);
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

  const sourceListContent = (
    <div className="space-y-4">
      {/* Media Sources */}
      <div>
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">📺 Media / Channels</h3>
        <div className="grid grid-cols-1 md:grid-cols-1 gap-1.5">
          {MEDIA_SOURCES.map((source) => (
            <label key={source.id} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-zinc-800/50 p-2 rounded transition-colors bg-zinc-900/30 border border-zinc-800/50">
              <input type="checkbox" checked={enabledSources[source.id] ?? source.enabled} onChange={() => toggleSource(source.id)} className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-red-500 focus:ring-red-500 focus:ring-offset-0" />
              <span className={enabledSources[source.id] ? 'text-white' : 'text-gray-500'}>{source.name}</span>
            </label>
          ))}
        </div>
      </div>
      
      {/* OSINT Sources */}
      <div>
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">🔍 OSINT / Verification / Safety</h3>
        <div className="grid grid-cols-1 md:grid-cols-1 gap-1.5">
          {OSINT_SOURCES.map((source) => (
            <label key={source.id} className={`flex items-center gap-2 text-xs cursor-pointer p-2 rounded transition-colors bg-zinc-900/30 border border-zinc-800/50 ${source.enabled ? 'hover:bg-zinc-800/50' : 'opacity-50'}`}>
              <input type="checkbox" checked={enabledSources[source.id] ?? source.enabled} onChange={() => source.enabled && toggleSource(source.id)} disabled={!source.enabled} className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0" />
              <span className={enabledSources[source.id] && source.enabled ? 'text-white' : 'text-gray-500'}>
                {source.icon && <span className="mr-1">{source.icon}</span>}
                {source.name}
              </span>
            </label>
          ))}
        </div>
      </div>
      
      {/* Other Sources */}
      <div>
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">📡 Other Sources</h3>
        <div className="grid grid-cols-1 md:grid-cols-1 gap-1.5">
          {OTHER_SOURCES.map((source) => (
            <label key={source.id} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-zinc-800/50 p-2 rounded transition-colors bg-zinc-900/30 border border-zinc-800/50">
              <input type="checkbox" checked={enabledSources[source.id] ?? source.enabled} onChange={() => toggleSource(source.id)} className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-purple-500 focus:ring-purple-500 focus:ring-offset-0" />
              <span className={enabledSources[source.id] ? 'text-white' : 'text-gray-500'}>{source.name}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <main className="relative w-screen h-screen bg-black overflow-hidden font-sans">
      <Map 
        events={filteredEvents} 
        onEventClick={setSelectedEvent}
        showPPU={viewMode !== 'verified'}
        airspaceData={airspaceData}
        showAirspace={showAirspace}
        connectivityData={connectivityData}
        showConnectivity={showConnectivity}
        onConnectivityClick={setSelectedProvince}
        mapStyle={mapStyle}
      />
      
      {/* Loading Overlay */}
      {(isInitialLoad || isRefreshing) && (
        <div className={`absolute inset-0 z-30 flex items-center justify-center pointer-events-none transition-opacity duration-300 ${isInitialLoad ? 'bg-black/80' : 'bg-transparent'}`}>
          <div className={`flex flex-col items-center gap-4 ${isInitialLoad ? 'scale-100' : 'absolute bottom-24 left-1/2 -translate-x-1/2'}`}>
            <div className={`relative ${isInitialLoad ? '' : 'bg-zinc-900/90 backdrop-blur px-4 py-2 rounded-full border border-zinc-700 shadow-lg'}`}>
              <div className="flex items-center gap-3">
                <Loader2 className={`${isInitialLoad ? 'w-8 h-8' : 'w-4 h-4'} text-red-500 animate-spin`} />
                <span className={`${isInitialLoad ? 'text-lg' : 'text-xs'} font-medium text-white`}>
                  {isInitialLoad ? 'Loading data...' : 'Refreshing...'}
                </span>
              </div>
            </div>
            {isInitialLoad && (
              <p className="text-sm text-gray-500 animate-pulse">Fetching latest reports</p>
            )}
          </div>
        </div>
      )}
      
      {/* Sidebar */}
      <Sidebar 
        event={selectedEvent} 
        onClose={() => setSelectedEvent(null)}
        stats={stats}
        isLoading={isInitialLoad}
      />
      
      {/* Telegram Feed */}
      <TelegramFeed 
        isOpen={showTelegramFeed}
        onClose={() => setShowTelegramFeed(false)}
      />
      
      {/* --- DESKTOP TOP BAR --- */}
      <div className="hidden md:flex absolute top-4 left-4 right-4 z-20 justify-between items-start pointer-events-none">
        {/* Left Controls Group */}
        <div className="pointer-events-auto flex flex-col gap-2">
          <div className="flex gap-2">
            {/* View Mode Group */}
            <div className="flex items-center bg-zinc-900/90 backdrop-blur border border-zinc-700 rounded-lg p-1 gap-1 shadow-lg">
              <button 
                onClick={() => setViewMode('all')}
                className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-colors ${viewMode === 'all' ? 'bg-red-900/50 text-red-400 shadow-sm' : 'text-gray-500 hover:text-white hover:bg-zinc-800'}`}
              >
                All
              </button>
              <button 
                onClick={() => setViewMode('ppu')}
                className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-colors ${viewMode === 'ppu' ? 'bg-blue-900/50 text-blue-400 shadow-sm' : 'text-gray-500 hover:text-white hover:bg-zinc-800'}`}
              >
                PPU
              </button>
              <button 
                onClick={() => setViewMode('verified')}
                className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-colors ${viewMode === 'verified' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-white hover:bg-zinc-800'}`}
              >
                Verified
              </button>
            </div>
            
            {/* Source Filter Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowSourceFilter(!showSourceFilter)}
                className={`flex items-center gap-2 h-full bg-zinc-900/90 backdrop-blur border px-3 py-2 rounded-lg text-xs font-medium transition-all hover:bg-zinc-800 shadow-lg ${
                  filterCount ? 'border-amber-600 text-amber-400' : 'border-zinc-700 text-white'
                }`}
              >
                <Filter className="w-3.5 h-3.5" />
                <span>Sources</span>
                {filterCount && <span className="bg-amber-600/20 text-amber-400 px-1.5 py-0.5 rounded text-[10px] font-bold">{filterCount}</span>}
              </button>
              
              {showSourceFilter && (
                <div className="absolute top-full left-0 mt-2 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-xl p-4 max-h-[70vh] overflow-y-auto w-80 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-200">
                  <div className="flex justify-between items-center mb-4 pb-2 border-b border-zinc-800">
                    <span className="text-sm font-bold text-white">Filter Sources</span>
                    <button onClick={() => setShowSourceFilter(false)}><X className="w-4 h-4 text-zinc-500 hover:text-white"/></button>
                  </div>
                  {sourceListContent}
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Right Controls Group */}
        <div className="pointer-events-auto flex items-center gap-2">
          {/* Feed Toggle */}
          <button
            onClick={() => setShowTelegramFeed(!showTelegramFeed)}
            className={`flex items-center gap-2 bg-zinc-900/90 backdrop-blur border px-3 py-2 rounded-lg text-xs font-medium transition-all shadow-lg ${
              showTelegramFeed ? 'border-blue-600 text-blue-400 bg-blue-900/20' : 'border-zinc-700 text-white hover:bg-zinc-800'
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${showTelegramFeed ? 'animate-pulse' : ''}`} />
            <span>Feed</span>
          </button>
          
          {/* Analytics Link */}
          <a href="/analytics" className="flex items-center gap-2 bg-zinc-900/90 backdrop-blur border border-zinc-700 px-3 py-2 rounded-lg text-xs font-medium transition-all text-white hover:bg-zinc-800 hover:border-violet-600 hover:text-violet-400 shadow-lg">
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Analytics</span>
          </a>
          
          {/* Summary Link */}
          <a href="/summary" className="flex items-center gap-2 bg-zinc-900/90 backdrop-blur border border-zinc-700 px-3 py-2 rounded-lg text-xs font-medium transition-all text-white hover:bg-zinc-800 hover:border-amber-600 hover:text-amber-400 shadow-lg">
            <span className="text-sm">📊</span>
            <span>Summary</span>
          </a>
          
          <div className="w-px h-6 bg-zinc-800 mx-1"></div>
          
          {/* Refresh Button */}
          <button
            onClick={() => fetchData(true)}
            disabled={isRefreshing}
            className="flex items-center gap-2 bg-zinc-900/90 backdrop-blur border border-zinc-700 px-3 py-2 rounded-lg text-xs font-medium transition-all hover:bg-zinc-800 text-white shadow-lg"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
          
          {/* Auto Toggle */}
          <button
            onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
            className={`flex items-center gap-1.5 bg-zinc-900/90 backdrop-blur border px-3 py-2 rounded-lg text-xs font-medium transition-all shadow-lg ${
              autoRefreshEnabled ? 'border-green-700 text-green-400 bg-green-900/10' : 'border-zinc-700 text-gray-500 hover:text-white'
            }`}
          >
            <div className={`w-1.5 h-1.5 rounded-full ${autoRefreshEnabled ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`} />
            <span>Auto</span>
          </button>
        </div>
      </div>
      
      {/* --- DESKTOP BOTTOM BAR (Layers) --- */}
      <div className="hidden md:flex absolute bottom-8 left-1/2 -translate-x-1/2 z-20 pointer-events-auto items-center gap-2 bg-zinc-900/90 backdrop-blur border border-zinc-700 p-1.5 rounded-full shadow-2xl">
        <button 
          className={`px-4 py-1.5 rounded-full uppercase text-[10px] font-bold tracking-widest transition-all whitespace-nowrap flex items-center gap-2 ${
            showAirspace ? 'bg-cyan-900/30 text-cyan-400 shadow-inner' : 'text-gray-500 hover:text-white hover:bg-zinc-800'
          }`}
          onClick={() => setShowAirspace(!showAirspace)}
        >
          <span>✈️ NOTAMs</span>
          {airspaceData.length > 0 && <span className="text-cyan-500 text-[9px] bg-cyan-900/50 px-1 rounded">{airspaceData.length}</span>}
        </button>
        
        <div className="w-px h-4 bg-zinc-700"></div>
        
        <button 
          className={`px-4 py-1.5 rounded-full uppercase text-[10px] font-bold tracking-widest transition-all whitespace-nowrap flex items-center gap-2 ${
            showConnectivity ? 'bg-green-900/30 text-green-400 shadow-inner' : 'text-gray-500 hover:text-white hover:bg-zinc-800'
          }`}
          onClick={() => setShowConnectivity(!showConnectivity)}
        >
          <span>📶 Internet</span>
          {nationalConnectivity && <span className="text-green-500 text-[9px] bg-green-900/50 px-1 rounded">{Math.round(nationalConnectivity.score * 100)}%</span>}
        </button>
        
        <div className="w-px h-4 bg-zinc-700"></div>
        
        {/* Map Style Picker */}
        <div className="relative group">
          <button className="px-4 py-1.5 rounded-full uppercase text-[10px] font-bold tracking-widest text-gray-400 hover:text-white hover:bg-zinc-800 transition-all flex items-center gap-2">
            <span>{MAP_STYLES[mapStyle].icon} Map Style</span>
          </button>
          
          {/* Hover Menu */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-40 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-xl overflow-hidden shadow-xl invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-all duration-200 p-1">
            {(Object.entries(MAP_STYLES) as [MapStyleName, typeof MAP_STYLES[MapStyleName]][]).map(([key, style]) => (
              <button
                key={key}
                className={`w-full px-3 py-2 text-left text-xs flex items-center gap-2 rounded-lg transition-colors ${mapStyle === key ? 'bg-zinc-800 text-white' : 'text-gray-400 hover:bg-zinc-800/50 hover:text-gray-200'}`}
                onClick={() => setMapStyle(key)}
              >
                <span>{style.icon}</span>
                <span>{style.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
      
      {/* --- MOBILE LAYOUT --- */}
      <div className="md:hidden absolute top-4 left-4 right-4 z-20 flex justify-between items-center pointer-events-none">
        <button onClick={() => setIsMenuOpen(true)} className="pointer-events-auto bg-zinc-900/90 p-3 rounded-xl text-white border border-zinc-700 shadow-lg backdrop-blur active:scale-95 transition-transform">
          <Menu className="w-6 h-6" />
        </button>
        
        <button onClick={() => fetchData(true)} className={`pointer-events-auto bg-zinc-900/90 p-3 rounded-xl text-white border border-zinc-700 shadow-lg backdrop-blur active:scale-95 transition-transform ${isRefreshing ? 'opacity-75' : ''}`}>
          <RefreshCw className={`w-6 h-6 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Mobile Menu Drawer */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-50 bg-zinc-950/95 backdrop-blur-xl flex flex-col animate-in fade-in slide-in-from-left-4 duration-200">
          <div className="flex justify-between items-center p-6 border-b border-zinc-800">
            <h2 className="text-xl font-bold text-white tracking-tight">Iran Map Control</h2>
            <button onClick={() => setIsMenuOpen(false)} className="p-2 text-zinc-400 hover:text-white bg-zinc-900 rounded-lg border border-zinc-800">
              <X className="w-6 h-6" />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-8">
            {/* View Mode Section */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">View Mode</h3>
              <div className="grid grid-cols-3 gap-2">
                <button 
                  onClick={() => setViewMode('all')} 
                  className={`p-3 rounded-xl text-sm font-bold border transition-all ${viewMode === 'all' ? 'bg-red-500/10 border-red-500/50 text-red-400' : 'bg-zinc-900 border-zinc-800 text-zinc-400'}`}
                >
                  All Events
                </button>
                <button 
                  onClick={() => setViewMode('ppu')} 
                  className={`p-3 rounded-xl text-sm font-bold border transition-all ${viewMode === 'ppu' ? 'bg-blue-500/10 border-blue-500/50 text-blue-400' : 'bg-zinc-900 border-zinc-800 text-zinc-400'}`}
                >
                  PPU Only
                </button>
                <button 
                  onClick={() => setViewMode('verified')} 
                  className={`p-3 rounded-xl text-sm font-bold border transition-all ${viewMode === 'verified' ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-400' : 'bg-zinc-900 border-zinc-800 text-zinc-400'}`}
                >
                  Verified
                </button>
              </div>
            </section>
            
            {/* Layers Section */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Map Layers</h3>
              <div className="grid grid-cols-1 gap-2">
                <button 
                  onClick={() => setShowAirspace(!showAirspace)}
                  className={`flex items-center justify-between p-4 rounded-xl border transition-all ${showAirspace ? 'bg-cyan-500/10 border-cyan-500/30' : 'bg-zinc-900 border-zinc-800'}`}
                >
                  <span className="flex items-center gap-3 text-sm font-medium text-zinc-200">
                    <span className="text-xl">✈️</span> NOTAM Restrictions
                  </span>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${showAirspace ? 'bg-cyan-500 border-cyan-500' : 'border-zinc-600'}`}>
                    {showAirspace && <div className="w-2 h-2 bg-white rounded-full" />}
                  </div>
                </button>
                
                <button 
                  onClick={() => setShowConnectivity(!showConnectivity)}
                  className={`flex items-center justify-between p-4 rounded-xl border transition-all ${showConnectivity ? 'bg-green-500/10 border-green-500/30' : 'bg-zinc-900 border-zinc-800'}`}
                >
                  <span className="flex items-center gap-3 text-sm font-medium text-zinc-200">
                    <span className="text-xl">📶</span> Internet Connectivity
                  </span>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${showConnectivity ? 'bg-green-500 border-green-500' : 'border-zinc-600'}`}>
                    {showConnectivity && <div className="w-2 h-2 bg-white rounded-full" />}
                  </div>
                </button>
              </div>
            </section>
            
            {/* Map Style Section */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Map Style</h3>
              <div className="grid grid-cols-3 gap-2">
                {(Object.entries(MAP_STYLES) as [MapStyleName, typeof MAP_STYLES[MapStyleName]][]).map(([key, style]) => (
                  <button
                    key={key}
                    onClick={() => setMapStyle(key)}
                    className={`flex flex-col items-center justify-center gap-2 p-3 rounded-xl border transition-all ${mapStyle === key ? 'bg-purple-500/10 border-purple-500/50 text-white' : 'bg-zinc-900 border-zinc-800 text-zinc-400'}`}
                  >
                    <span className="text-2xl">{style.icon}</span>
                    <span className="text-xs font-medium">{style.label}</span>
                  </button>
                ))}
              </div>
            </section>
            
            {/* Tools Links */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Tools & Analysis</h3>
              <div className="grid grid-cols-2 gap-2">
                <a href="/analytics" className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex flex-col gap-2 hover:bg-zinc-800 transition-colors">
                  <BarChart3 className="w-6 h-6 text-violet-400" />
                  <span className="text-sm font-bold text-white">Analytics Dashboard</span>
                </a>
                <a href="/summary" className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex flex-col gap-2 hover:bg-zinc-800 transition-colors">
                  <span className="text-2xl">📊</span>
                  <span className="text-sm font-bold text-white">AI Summary</span>
                </a>
              </div>
              
               <button 
                  onClick={() => setShowTelegramFeed(!showTelegramFeed)}
                  className={`w-full p-4 rounded-xl border flex items-center gap-3 transition-all ${showTelegramFeed ? 'bg-blue-500/10 border-blue-500/30' : 'bg-zinc-900 border-zinc-800'}`}
                >
                  <Radio className={`w-5 h-5 ${showTelegramFeed ? 'text-blue-400 animate-pulse' : 'text-zinc-500'}`} />
                  <span className="text-sm font-bold text-zinc-200">Telegram Live Feed</span>
                </button>
            </section>
            
            {/* Source Filters */}
            <section className="space-y-3 pt-4 border-t border-zinc-800">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Data Sources</h3>
              <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
                {sourceListContent}
              </div>
            </section>
          </div>
        </div>
      )}

      {/* Popups */}
      {selectedProvince && showConnectivity && (
        <div className="absolute top-20 left-4 right-4 md:left-1/2 md:-translate-x-1/2 md:right-auto z-30 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-xl p-4 shadow-xl max-w-sm mx-auto">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-white">{selectedProvince.properties.name}</h3>
            <button 
              onClick={() => setSelectedProvince(null)}
              className="text-zinc-400 hover:text-white text-lg w-8 h-8 flex items-center justify-center rounded-full hover:bg-zinc-800"
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
    </main>
  );
}