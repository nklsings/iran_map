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
  hourly_pattern: Record<number, number>;
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
  hourly_distribution: Record<number, number>;
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
  data: Record<number, number>;
  maxValue: number;
}) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 24 }, (_, hour) => {
        const count = data[hour] || 0;
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
        const apiUrl =
          process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        const [summaryRes, citiesRes] = await Promise.all([
          fetch(`${apiUrl}/api/analytics/summary`),
          fetch(`${apiUrl}/api/analytics/cities?limit=30`),
        ]);

        if (!summaryRes.ok || !citiesRes.ok) {
          throw new Error('Failed to fetch analytics');
        }

        const summaryData = await summaryRes.json();
        const citiesData = await citiesRes.json();

        setSummary(summaryData.summary);
        setCities(citiesData.cities);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load');
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

  const maxHourly = summary
    ? Math.max(...Object.values(summary.hourly_distribution), 1)
    : 1;

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-gray-400 hover:text-white transition-colors"
            >
              ← Back to Map
            </Link>
            <h1 className="text-2xl font-bold">📊 City Analytics</h1>
          </div>
          <div className="text-sm text-gray-400">
            Last updated: {new Date().toLocaleTimeString()}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Key Stats */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold text-blue-400">
                {summary.total_events.toLocaleString()}
              </div>
              <div className="text-sm text-gray-400">Total Events</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold text-green-400">
                {summary.events_24h}
              </div>
              <div className="text-sm text-gray-400">Last 24h</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold text-purple-400">
                {summary.events_7d}
              </div>
              <div className="text-sm text-gray-400">Last 7 Days</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold text-yellow-400">
                {summary.total_cities}
              </div>
              <div className="text-sm text-gray-400">Cities</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-xl font-bold text-orange-400">
                {summary.most_active_city || 'N/A'}
              </div>
              <div className="text-sm text-gray-400">Most Active</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-xl font-bold text-red-400">
                {summary.most_active_hour !== null
                  ? formatHour(summary.most_active_hour)
                  : 'N/A'}
              </div>
              <div className="text-sm text-gray-400">Peak Hour</div>
            </div>
          </div>
        )}

        {/* Hourly Distribution */}
        {summary && (
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">
              📅 24-Hour Activity Pattern
            </h2>
            <div className="flex items-end gap-1 h-32">
              {Array.from({ length: 24 }, (_, hour) => {
                const count = summary.hourly_distribution[hour] || 0;
                const height =
                  maxHourly > 0 ? (count / maxHourly) * 100 : 0;
                const isNow = new Date().getHours() === hour;

                return (
                  <div
                    key={hour}
                    className="flex-1 flex flex-col items-center"
                  >
                    <div
                      className={`w-full rounded-t transition-all ${
                        isNow
                          ? 'bg-blue-500'
                          : height > 75
                            ? 'bg-red-500'
                            : height > 50
                              ? 'bg-orange-500'
                              : height > 25
                                ? 'bg-yellow-500'
                                : 'bg-gray-600'
                      }`}
                      style={{ height: `${Math.max(height, 4)}%` }}
                      title={`${formatHour(hour)}: ${count} events`}
                    />
                    {hour % 3 === 0 && (
                      <span className="text-xs text-gray-500 mt-1">
                        {formatHour(hour)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="mt-2 text-xs text-gray-500 text-center">
              Local time distribution (Iran Standard Time)
            </div>
          </div>
        )}

        {/* Event Type Distribution */}
        {summary && (
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">📊 Event Types</h2>
            <div className="flex flex-wrap gap-4">
              {Object.entries(summary.event_type_distribution).map(
                ([type, count]) => (
                  <div key={type} className="flex items-center gap-2">
                    <div
                      className={`w-3 h-3 rounded ${EVENT_TYPE_COLORS[type] || 'bg-gray-500'}`}
                    />
                    <span className="capitalize">{type.replace('_', ' ')}</span>
                    <span className="text-gray-400">({count})</span>
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {/* City Rankings */}
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-gray-700">
            <h2 className="text-lg font-semibold">🏙️ City Rankings</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-700/50 text-sm text-gray-400">
                <tr>
                  <th className="p-3 text-left">#</th>
                  <th className="p-3 text-left">City</th>
                  <th className="p-3 text-center">24h</th>
                  <th className="p-3 text-center">7d</th>
                  <th className="p-3 text-center">Total</th>
                  <th className="p-3 text-center">Trend</th>
                  <th className="p-3 text-center">Activity</th>
                  <th className="p-3 text-center">Peak</th>
                  <th className="p-3 text-left">Hourly Pattern</th>
                </tr>
              </thead>
              <tbody>
                {cities.map((city) => (
                  <tr
                    key={city.city_name}
                    className="border-b border-gray-700/50 hover:bg-gray-700/30 cursor-pointer"
                    onClick={() => setSelectedCity(city)}
                  >
                    <td className="p-3 text-gray-500">{city.rank}</td>
                    <td className="p-3">
                      <div className="font-medium">{city.city_name}</div>
                      <div className="text-sm text-gray-500">
                        {city.city_name_fa} • {city.province}
                      </div>
                    </td>
                    <td className="p-3 text-center">
                      <span
                        className={
                          city.events_24h > 5
                            ? 'text-red-400 font-bold'
                            : city.events_24h > 0
                              ? 'text-yellow-400'
                              : 'text-gray-500'
                        }
                      >
                        {city.events_24h}
                      </span>
                    </td>
                    <td className="p-3 text-center text-blue-400">
                      {city.events_7d}
                    </td>
                    <td className="p-3 text-center">{city.total_events}</td>
                    <td className="p-3 text-center">
                      <span title={`${city.trend_percentage.toFixed(1)}%`}>
                        {TREND_ICONS[city.trend_direction] || '➡️'}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <span
                        className={`px-2 py-1 rounded text-xs ${ACTIVITY_COLORS[city.activity_level]} text-white`}
                      >
                        {city.activity_level}
                      </span>
                    </td>
                    <td className="p-3 text-center text-sm text-gray-400">
                      {city.peak_hour !== null
                        ? formatHour(city.peak_hour)
                        : '-'}
                    </td>
                    <td className="p-3">
                      {city.hourly_pattern && (
                        <HourlyHeatmap
                          data={city.hourly_pattern}
                          maxValue={Math.max(
                            ...Object.values(city.hourly_pattern),
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
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg p-6 max-w-lg w-full mx-4 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold">
                  {selectedCity.city_name} ({selectedCity.city_name_fa})
                </h3>
                <button
                  onClick={() => setSelectedCity(null)}
                  className="text-gray-400 hover:text-white"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-700/50 rounded p-3">
                    <div className="text-2xl font-bold text-blue-400">
                      {selectedCity.events_24h}
                    </div>
                    <div className="text-sm text-gray-400">Last 24 hours</div>
                  </div>
                  <div className="bg-gray-700/50 rounded p-3">
                    <div className="text-2xl font-bold text-purple-400">
                      {selectedCity.events_7d}
                    </div>
                    <div className="text-sm text-gray-400">Last 7 days</div>
                  </div>
                </div>

                <div className="bg-gray-700/50 rounded p-3">
                  <div className="text-sm text-gray-400 mb-2">
                    Event Breakdown
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      ✊ Protests: <strong>{selectedCity.protest_count}</strong>
                    </div>
                    <div>
                      ⚔️ Clashes: <strong>{selectedCity.clash_count}</strong>
                    </div>
                    <div>
                      🚔 Arrests: <strong>{selectedCity.arrest_count}</strong>
                    </div>
                    <div>
                      🚨 Police: <strong>{selectedCity.police_count}</strong>
                    </div>
                    <div>
                      🛑 Strikes: <strong>{selectedCity.strike_count}</strong>
                    </div>
                    <div>
                      📊 Total: <strong>{selectedCity.total_events}</strong>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-700/50 rounded p-3">
                  <div className="text-sm text-gray-400 mb-2">Trend</div>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">
                      {TREND_ICONS[selectedCity.trend_direction]}
                    </span>
                    <span
                      className={
                        selectedCity.trend_percentage > 0
                          ? 'text-green-400'
                          : selectedCity.trend_percentage < 0
                            ? 'text-red-400'
                            : 'text-gray-400'
                      }
                    >
                      {selectedCity.trend_percentage > 0 ? '+' : ''}
                      {selectedCity.trend_percentage.toFixed(1)}% vs previous
                      week
                    </span>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Link
                    href={`/?lat=${selectedCity.latitude}&lon=${selectedCity.longitude}&zoom=12`}
                    className="flex-1 px-4 py-2 bg-blue-600 rounded text-center hover:bg-blue-700"
                  >
                    📍 View on Map
                  </Link>
                  <button
                    onClick={() => setSelectedCity(null)}
                    className="px-4 py-2 bg-gray-600 rounded hover:bg-gray-500"
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

