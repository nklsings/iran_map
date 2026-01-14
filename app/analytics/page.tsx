'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

interface CityStats {
  rank: number;
  city_name: string;
  city_name_fa: string;
  latitude: number;
  longitude: number;
  province: string;
  total_events: number;
  protest_count: number;
  clash_count: number;
  arrest_count: number;
  police_count: number;
  strike_count: number;
  events_24h: number;
  events_7d: number;
  trend_direction: string;
  trend_percentage: number;
  hourly_pattern: Record<string, number>;  // JSON keys are always strings
  peak_hour: number | null;
  avg_daily_events: number;
  activity_level: string;
}

interface AnalyticsSummary {
  total_cities: number;
  total_events: number;
  events_24h: number;
  events_7d: number;
  most_active_city: string | null;
  most_active_hour: number | null;
  top_cities: CityStats[];
  hourly_distribution: Record<string, number>;  // JSON keys are always strings
  event_type_distribution: Record<string, number>;
}

const ACTIVITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-gray-500',
};

const TREND_ICONS: Record<string, string> = {
  up: '📈',
  down: '📉',
  stable: '➡️',
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  protest: 'bg-purple-500',
  clash: 'bg-red-500',
  arrest: 'bg-orange-500',
  police_presence: 'bg-yellow-500',
  strike: 'bg-blue-500',
};

function formatHour(hour: number): string {
  const h = hour % 12 || 12;
  const ampm = hour < 12 ? 'AM' : 'PM';
  return `${h}${ampm}`;
}

function HourlyHeatmap({
  data,
  maxValue,
}: {
  data: Record<string, number>;  // JSON keys are strings
  maxValue: number;
}) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 24 }, (_, hour) => {
        // Access with string key since JSON keys are strings
        const count = Number(data[String(hour)]) || 0;
        const intensity = maxValue > 0 ? count / maxValue : 0;
        const bg =
          intensity > 0.8
            ? 'bg-red-500'
            : intensity > 0.6
              ? 'bg-orange-500'
              : intensity > 0.4
                ? 'bg-yellow-500'
                : intensity > 0.2
                  ? 'bg-green-500'
                  : intensity > 0
                    ? 'bg-blue-500'
                    : 'bg-gray-700';

        return (
          <div
            key={hour}
            className={`w-3 h-6 rounded-sm ${bg} cursor-pointer`}
            title={`${formatHour(hour)}: ${count} events`}
          />
        );
      })}
    </div>
  );
}

function SparklineTrend({
  data,
  height = 30,
}: {
  data: number[];
  height?: number;
}) {
  const max = Math.max(...data, 1);
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = height - (v / max) * height;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width="100" height={height} className="inline-block">
      <polyline
        fill="none"
        stroke="#60a5fa"
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [cities, setCities] = useState<CityStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCity, setSelectedCity] = useState<CityStats | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout

        const [summaryRes, citiesRes] = await Promise.all([
          fetch(`${apiUrl}/api/analytics/summary`, { signal: controller.signal }),
          fetch(`${apiUrl}/api/analytics/cities?limit=30`, { signal: controller.signal }),
        ]);
        
        clearTimeout(timeoutId);

        if (!summaryRes.ok || !citiesRes.ok) {
          throw new Error('Failed to fetch analytics');
        }

        const summaryData = await summaryRes.json();
        const citiesData = await citiesRes.json();
        
        // Handle warning responses
        if (summaryData.warning || citiesData.warning) {
          console.warn('Analytics warning:', summaryData.warning || citiesData.warning);
        }

        setSummary(summaryData.summary);
        setCities(citiesData.cities || []);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setError('Request timed out. Analytics service may be slow.');
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 300000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin text-6xl mb-4">📊</div>
          <p className="text-gray-400">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 text-xl mb-4">⚠️ {error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Get hourly values - convert string keys to ensure proper access
  const hourlyValues = summary 
    ? Object.values(summary.hourly_distribution).map(v => Number(v) || 0)
    : [];
  const maxHourly = hourlyValues.length > 0 
    ? Math.max(...hourlyValues, 1) 
    : 1;

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-zinc-900/95 backdrop-blur border-b border-zinc-800">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-zinc-400 hover:text-white transition-colors"
            >
              ← Back to Map
            </Link>
            <h1 className="text-xl font-bold tracking-tight">📊 City Analytics</h1>
          </div>
          <div className="text-sm text-zinc-400">
            Last updated: {new Date().toLocaleTimeString()}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Key Stats */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
              <div className="text-3xl font-bold text-blue-400">
                {summary.total_events.toLocaleString()}
              </div>
              <div className="text-sm text-zinc-500 mt-1 uppercase tracking-wide">Total Events</div>
            </div>
            <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
              <div className="text-3xl font-bold text-green-400">
                {summary.events_24h}
              </div>
              <div className="text-sm text-zinc-500 mt-1 uppercase tracking-wide">Last 24h</div>
            </div>
            <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
              <div className="text-3xl font-bold text-purple-400">
                {summary.events_7d}
              </div>
              <div className="text-sm text-zinc-500 mt-1 uppercase tracking-wide">Last 7 Days</div>
            </div>
            <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
              <div className="text-3xl font-bold text-yellow-400">
                {summary.total_cities}
              </div>
              <div className="text-sm text-zinc-500 mt-1 uppercase tracking-wide">Cities</div>
            </div>
            <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
              <div className="text-xl font-bold text-orange-400 truncate" title={summary.most_active_city || 'N/A'}>
                {summary.most_active_city || 'N/A'}
              </div>
              <div className="text-sm text-zinc-500 mt-1 uppercase tracking-wide">Most Active</div>
            </div>
            <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
              <div className="text-xl font-bold text-red-400">
                {summary.most_active_hour !== null
                  ? formatHour(summary.most_active_hour)
                  : 'N/A'}
              </div>
              <div className="text-sm text-zinc-500 mt-1 uppercase tracking-wide">Peak Hour</div>
            </div>
          </div>
        )}

        {/* Hourly Distribution */}
        {summary && (
          <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
            <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
              <span className="text-xl">📅</span> 24-Hour Activity Pattern
            </h2>
            <div className="flex items-end gap-1 h-32 mb-6">
              {Array.from({ length: 24 }, (_, hour) => {
                // Access with string key since JSON keys are strings
                const count = Number(summary.hourly_distribution[String(hour)]) || 0;
                const heightPercent =
                  maxHourly > 0 ? (count / maxHourly) * 100 : 0;
                // Calculate actual pixel height based on container (128px = h-32)
                const barHeight = Math.max((heightPercent / 100) * 128, 4);
                const isNow = new Date().getHours() === hour;

                return (
                  <div
                    key={hour}
                    className="flex-1 flex flex-col justify-end items-center group relative h-full"
                  >
                    <div
                      className={`w-full rounded-t transition-all ${
                        isNow
                          ? 'bg-blue-500'
                          : heightPercent > 75
                            ? 'bg-red-500'
                            : heightPercent > 50
                              ? 'bg-orange-500'
                              : heightPercent > 25
                                ? 'bg-yellow-500'
                                : 'bg-zinc-700'
                      }`}
                      style={{ height: `${barHeight}px` }}
                    />
                    {/* Tooltip */}
                    <div className="absolute bottom-full mb-2 bg-zinc-800 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 border border-zinc-700 pointer-events-none">
                      {formatHour(hour)}: {count} events
                    </div>
                    
                    {hour % 3 === 0 && (
                      <span className="text-[10px] text-zinc-500 mt-2 absolute -bottom-5 font-mono">
                        {formatHour(hour)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="mt-4 text-xs text-zinc-500 text-center font-mono">
              Local time distribution (Iran Standard Time)
            </div>
          </div>
        )}

        {/* Event Type Distribution */}
        {summary && (
          <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
            <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
              <span className="text-xl">📊</span> Event Types
            </h2>
            <div className="flex flex-wrap gap-4">
              {Object.entries(summary.event_type_distribution).map(
                ([type, count]) => (
                  <div key={type} className="flex items-center gap-2 bg-zinc-800/50 px-3 py-2 rounded-lg border border-zinc-700">
                    <div
                      className={`w-3 h-3 rounded-full ${EVENT_TYPE_COLORS[type] || 'bg-zinc-500'}`}
                    />
                    <span className="capitalize font-medium text-zinc-200">{type.replace('_', ' ')}</span>
                    <span className="text-zinc-400 font-mono">({count})</span>
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {/* City Rankings */}
        <div className="bg-zinc-900 rounded-xl overflow-hidden border border-zinc-800">
          <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <span className="text-xl">🏙️</span> City Rankings
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-zinc-800/50 text-xs font-bold text-zinc-400 uppercase tracking-wider">
                <tr>
                  <th className="p-4 text-left">#</th>
                  <th className="p-4 text-left">City</th>
                  <th className="p-4 text-center">24h</th>
                  <th className="p-4 text-center">7d</th>
                  <th className="p-4 text-center">Total</th>
                  <th className="p-4 text-center">Trend</th>
                  <th className="p-4 text-center">Activity</th>
                  <th className="p-4 text-center">Peak</th>
                  <th className="p-4 text-left">Hourly Pattern</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {cities.map((city) => (
                  <tr
                    key={city.city_name}
                    className="hover:bg-zinc-800/30 cursor-pointer transition-colors"
                    onClick={() => setSelectedCity(city)}
                  >
                    <td className="p-4 text-zinc-500 font-mono">{city.rank}</td>
                    <td className="p-4">
                      <div className="font-bold text-white">{city.city_name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">
                        {city.city_name_fa} • {city.province}
                      </div>
                    </td>
                    <td className="p-4 text-center">
                      <span
                        className={`font-mono font-bold ${
                          city.events_24h > 5
                            ? 'text-red-400'
                            : city.events_24h > 0
                              ? 'text-yellow-400'
                              : 'text-zinc-500'
                        }`}
                      >
                        {city.events_24h}
                      </span>
                    </td>
                    <td className="p-4 text-center text-blue-400 font-mono">
                      {city.events_7d}
                    </td>
                    <td className="p-4 text-center text-zinc-300 font-mono">{city.total_events}</td>
                    <td className="p-4 text-center">
                      <span title={`${city.trend_percentage.toFixed(1)}%`} className="text-lg">
                        {TREND_ICONS[city.trend_direction] || '➡️'}
                      </span>
                    </td>
                    <td className="p-4 text-center">
                      <span
                        className={`px-2 py-1 rounded text-xs font-bold uppercase ${ACTIVITY_COLORS[city.activity_level]} text-white`}
                      >
                        {city.activity_level}
                      </span>
                    </td>
                    <td className="p-4 text-center text-xs text-zinc-400 font-mono">
                      {city.peak_hour !== null
                        ? formatHour(city.peak_hour)
                        : '-'}
                    </td>
                    <td className="p-4">
                      {city.hourly_pattern && (
                        <HourlyHeatmap
                          data={city.hourly_pattern}
                          maxValue={Math.max(
                            ...Object.values(city.hourly_pattern).map(v => Number(v) || 0),
                            1
                          )}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* City Detail Modal */}
        {selectedCity && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
            <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-lg w-full shadow-2xl animate-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-2xl font-bold text-white">
                    {selectedCity.city_name}
                  </h3>
                  <p className="text-zinc-400 text-sm mt-1">{selectedCity.city_name_fa}</p>
                </div>
                <button
                  onClick={() => setSelectedCity(null)}
                  className="p-2 text-zinc-400 hover:text-white bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                    <div className="text-2xl font-bold text-blue-400 font-mono">
                      {selectedCity.events_24h}
                    </div>
                    <div className="text-xs text-zinc-500 uppercase tracking-wide mt-1">Last 24 hours</div>
                  </div>
                  <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                    <div className="text-2xl font-bold text-purple-400 font-mono">
                      {selectedCity.events_7d}
                    </div>
                    <div className="text-xs text-zinc-500 uppercase tracking-wide mt-1">Last 7 days</div>
                  </div>
                </div>

                <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                  <div className="text-xs text-zinc-500 uppercase tracking-wide mb-3">
                    Event Breakdown
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">✊ Protests</span>
                      <strong className="font-mono text-white">{selectedCity.protest_count}</strong>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">⚔️ Clashes</span>
                      <strong className="font-mono text-white">{selectedCity.clash_count}</strong>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">🚔 Arrests</span>
                      <strong className="font-mono text-white">{selectedCity.arrest_count}</strong>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">🚨 Police</span>
                      <strong className="font-mono text-white">{selectedCity.police_count}</strong>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">🛑 Strikes</span>
                      <strong className="font-mono text-white">{selectedCity.strike_count}</strong>
                    </div>
                    <div className="pt-2 mt-2 border-t border-zinc-700/50 flex justify-between items-center">
                      <span className="font-bold text-zinc-200">Total</span>
                      <strong className="font-mono text-white">{selectedCity.total_events}</strong>
                    </div>
                  </div>
                </div>

                <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                  <div className="text-xs text-zinc-500 uppercase tracking-wide mb-3">Trend</div>
                  <div className="flex items-center gap-3">
                    <span className="text-3xl bg-zinc-900 p-2 rounded-lg border border-zinc-700">
                      {TREND_ICONS[selectedCity.trend_direction]}
                    </span>
                    <div>
                      <div
                        className={`text-lg font-bold ${
                          selectedCity.trend_percentage > 0
                            ? 'text-green-400'
                            : selectedCity.trend_percentage < 0
                              ? 'text-red-400'
                              : 'text-zinc-400'
                        }`}
                      >
                        {selectedCity.trend_percentage > 0 ? '+' : ''}
                        {selectedCity.trend_percentage.toFixed(1)}%
                      </div>
                      <div className="text-xs text-zinc-500">vs previous week</div>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <Link
                    href={`/?lat=${selectedCity.latitude}&lon=${selectedCity.longitude}&zoom=12`}
                    className="flex-1 px-4 py-3 bg-blue-600 rounded-xl text-center font-semibold hover:bg-blue-500 transition-colors flex items-center justify-center gap-2"
                  >
                    <span>📍</span> View on Map
                  </Link>
                  <button
                    onClick={() => setSelectedCity(null)}
                    className="px-6 py-3 bg-zinc-800 rounded-xl hover:bg-zinc-700 transition-colors font-semibold border border-zinc-700"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

