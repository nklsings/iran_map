"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface HotspotInfo {
  city: string;
  activity_level: string;
  notes: string;
}

interface SummaryData {
  id: number;
  title: string;
  summary: string;
  key_developments: string[];
  hotspots: HotspotInfo[];
  risk_assessment: string;
  stats: {
    total: number;
    protests: number;
    clashes: number;
    arrests: number;
    police_presence: number;
  };
  period: {
    start: string;
    end: string;
    hours: number;
  };
  generated_at: string;
  model: string;
  tokens_used: number;
  generation_time_ms: number;
}

interface SummaryResponse {
  status: string;
  summary: SummaryData | null;
  message?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Risk level colors
const getRiskColor = (assessment: string) => {
  const text = assessment.toLowerCase();
  if (text.includes("critical")) return "text-red-500 bg-red-500/20 border-red-500";
  if (text.includes("high")) return "text-orange-500 bg-orange-500/20 border-orange-500";
  if (text.includes("elevated")) return "text-amber-500 bg-amber-500/20 border-amber-500";
  if (text.includes("moderate")) return "text-yellow-500 bg-yellow-500/20 border-yellow-500";
  if (text.includes("low")) return "text-green-500 bg-green-500/20 border-green-500";
  return "text-gray-400 bg-gray-500/20 border-gray-500";
};

const getActivityColor = (level: string) => {
  switch (level.toLowerCase()) {
    case "high": return "text-red-400 bg-red-500/20";
    case "medium": return "text-amber-400 bg-amber-500/20";
    case "low": return "text-green-400 bg-green-500/20";
    default: return "text-gray-400 bg-gray-500/20";
  }
};

export default function SummaryPage() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [history, setHistory] = useState<SummaryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API_URL}/api/summary`);
      const data: SummaryResponse = await res.json();
      
      if (data.status === "success" && data.summary) {
        setSummary(data.summary);
        setError(null);
      } else if (data.status === "no_data") {
        setError("No events to summarize yet. Check back later.");
      }
    } catch (err) {
      setError("Failed to fetch summary. Backend may be unavailable.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/api/summary/history?limit=24`);
      const data = await res.json();
      if (data.status === "success") {
        setHistory(data.summaries);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    }
  };

  const refreshSummary = async () => {
    setRefreshing(true);
    try {
      const res = await fetch(`${API_URL}/api/summary/generate`, { method: "POST" });
      const data = await res.json();
      if (data.status === "success" && data.summary) {
        setSummary(data.summary);
      }
    } catch (err) {
      console.error("Failed to refresh:", err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchSummary();
    fetchHistory();
    
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchSummary, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
          <p className="text-zinc-400">Loading situation summary...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-zinc-900/95 backdrop-blur border-b border-zinc-800">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link 
              href="/"
              className="text-zinc-400 hover:text-white transition-colors"
            >
              ← Map
            </Link>
            <div>
              <h1 className="text-xl font-bold tracking-tight">
                📊 Situation Summary
              </h1>
              <p className="text-xs text-zinc-500">
                AI-Generated Intelligence Report
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                showHistory 
                  ? "bg-amber-500/20 text-amber-400 border border-amber-500/50" 
                  : "bg-zinc-800 text-zinc-400 hover:text-white"
              }`}
            >
              📜 History
            </button>
            <button
              onClick={refreshSummary}
              disabled={refreshing}
              className="px-3 py-2 bg-amber-500/20 text-amber-400 rounded-lg text-sm font-medium hover:bg-amber-500/30 transition-colors disabled:opacity-50"
            >
              {refreshing ? "⏳" : "🔄"} Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {error ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📭</div>
            <p className="text-zinc-400">{error}</p>
          </div>
        ) : summary ? (
          <div className="space-y-8">
            {/* Title and Meta */}
            <div className="text-center">
              <h2 className="text-2xl md:text-3xl font-bold mb-2">
                {summary.title}
              </h2>
              <p className="text-zinc-500 text-sm">
                Generated {formatTime(summary.generated_at)} • 
                Covering {summary.period.hours}h period • 
                {summary.model !== "fallback" && (
                  <span className="text-amber-500"> AI-Powered</span>
                )}
              </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <StatCard label="Total Events" value={summary.stats.total} color="text-white" />
              <StatCard label="Protests" value={summary.stats.protests} color="text-amber-400" icon="✊" />
              <StatCard label="Clashes" value={summary.stats.clashes} color="text-red-400" icon="⚔️" />
              <StatCard label="Arrests" value={summary.stats.arrests} color="text-orange-400" icon="🔒" />
              <StatCard label="Police" value={summary.stats.police_presence} color="text-blue-400" icon="🚨" />
            </div>

            {/* Risk Assessment */}
            <div className={`p-4 rounded-xl border ${getRiskColor(summary.risk_assessment)}`}>
              <h3 className="font-bold mb-2 uppercase text-sm tracking-wider">Risk Assessment</h3>
              <p className="text-sm opacity-90">{summary.risk_assessment}</p>
            </div>

            {/* Main Summary */}
            <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
              <h3 className="font-bold mb-4 text-lg">Executive Summary</h3>
              <div className="prose prose-invert prose-sm max-w-none">
                {summary.summary.split("\n\n").map((paragraph, i) => (
                  <p key={i} className="text-zinc-300 leading-relaxed mb-4">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Key Developments */}
              <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
                <h3 className="font-bold mb-4 text-lg">🔑 Key Developments</h3>
                <ul className="space-y-3">
                  {summary.key_developments.map((dev, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="text-amber-500 font-bold">{i + 1}.</span>
                      <span className="text-zinc-300 text-sm">{dev}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Hotspots */}
              <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
                <h3 className="font-bold mb-4 text-lg">📍 Active Hotspots</h3>
                {summary.hotspots.length > 0 ? (
                  <ul className="space-y-3">
                    {summary.hotspots.map((spot, i) => (
                      <li key={i} className="flex items-center gap-3">
                        <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${getActivityColor(spot.activity_level)}`}>
                          {spot.activity_level}
                        </span>
                        <div>
                          <span className="font-medium">{spot.city}</span>
                          {spot.notes && (
                            <span className="text-zinc-500 text-sm ml-2">— {spot.notes}</span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-zinc-500 text-sm">No specific hotspots identified</p>
                )}
              </div>
            </div>

            {/* Generation Info */}
            <div className="text-center text-xs text-zinc-600">
              Generated by {summary.model} • {summary.tokens_used} tokens • {summary.generation_time_ms}ms
            </div>
          </div>
        ) : null}

        {/* History Panel */}
        {showHistory && history.length > 0 && (
          <div className="mt-12 pt-8 border-t border-zinc-800">
            <h3 className="text-xl font-bold mb-6">📜 Summary History</h3>
            <div className="space-y-4">
              {history.map((h) => (
                <div 
                  key={h.id}
                  className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                    h.id === summary?.id 
                      ? "bg-amber-500/10 border-amber-500/50" 
                      : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
                  }`}
                  onClick={() => setSummary(h)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm">{h.title}</span>
                    <span className="text-xs text-zinc-500">{formatTime(h.generated_at)}</span>
                  </div>
                  <div className="flex gap-4 text-xs text-zinc-400">
                    <span>{h.stats.total} events</span>
                    <span>{h.stats.protests} protests</span>
                    <span>{h.stats.clashes} clashes</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 mt-12 py-6">
        <div className="max-w-6xl mx-auto px-4 text-center text-xs text-zinc-600">
          Summaries are AI-generated and may not reflect all events. 
          Always verify critical information from primary sources.
        </div>
      </footer>
    </div>
  );
}

function StatCard({ 
  label, 
  value, 
  color, 
  icon 
}: { 
  label: string; 
  value: number; 
  color: string;
  icon?: string;
}) {
  return (
    <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800 text-center">
      <div className={`text-3xl font-bold ${color}`}>
        {icon && <span className="mr-1 text-2xl">{icon}</span>}
        {value}
      </div>
      <div className="text-xs text-zinc-500 mt-1 uppercase tracking-wide">{label}</div>
    </div>
  );
}

