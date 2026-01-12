// Event type constants
export type EventType = "protest" | "police_presence" | "strike" | "clash" | "arrest";
export type SourcePlatform = "telegram" | "reddit" | "instagram" | "youtube" | "rss" | "twitter" | "crowdsourced" | "multiple" | "admin";
export type SourceCategory = "media" | "osint" | "verification" | "safety";

// Source definitions for filter UI
export interface SourceDefinition {
  id: string;
  name: string;
  category: SourceCategory;
  enabled: boolean;
  icon?: string;
  patterns: string[]; // Patterns to match in event titles/source URLs
}

// Media channels
export const MEDIA_SOURCES: SourceDefinition[] = [
  { id: "bbc_persian", name: "BBC Persian", category: "media", enabled: true, patterns: ["bbc persian", "bbcpersian", "@bbcpersian"] },
  { id: "iran_intl", name: "IRAN INTL", category: "media", enabled: true, patterns: ["iran international", "iranintl", "@iranintl", "iran intl"] },
  { id: "bayan", name: "Bayan", category: "media", enabled: true, patterns: ["bayan", "@bayan"] },
  { id: "euronews_fa", name: "Euro News FA", category: "media", enabled: true, patterns: ["euronews", "euro news", "@euronews"] },
  { id: "iranefarda", name: "Iranefarda", category: "media", enabled: true, patterns: ["iranefarda", "iran efarda", "@iranefarda"] },
  { id: "afghan_intl", name: "Afghan Intl", category: "media", enabled: true, patterns: ["afghan intl", "afghanintl", "@afghanintl", "afi.tv"] },
  { id: "manzarpour", name: "Mohammad Manzarpour", category: "media", enabled: true, patterns: ["manzarpour", "@manzarpour", "@mohammadmanzarpour"] },
  { id: "radis", name: "Radis", category: "media", enabled: true, patterns: ["radis", "@radis"] },
];

// OSINT / Verification / Safety sources
export const OSINT_SOURCES: SourceDefinition[] = [
  { id: "geoconfirmed", name: "GeoConfirmed", category: "osint", enabled: true, icon: "🌍", patterns: ["geoconfirmed", "@geoconfirmed", "[geoconfirmed]"] },
  { id: "arcgis", name: "ArcGIS Intel", category: "osint", enabled: true, icon: "🗺️", patterns: ["[arcgis]", "arcgis feature", "missile base", "nuclear site", "naval base", "power plant", "israeli operation"] },
  { id: "mahsaalert", name: "MahsaAlert", category: "safety", enabled: true, icon: "🚨", patterns: ["mahsaalert", "@mahsaalert", "mahsa alert"] },
  { id: "factnameh", name: "FactNameh", category: "verification", enabled: true, icon: "✓", patterns: ["factnameh", "@factnameh", "fact nameh"] },
  { id: "notams", name: "NOTAMs", category: "safety", enabled: true, icon: "✈️", patterns: ["notam", "notams"] },
  { id: "flight24", name: "Flight24", category: "safety", enabled: false, icon: "🛫", patterns: ["flight24", "flightradar", "flightradar24"] },
];

// Other sources (Reddit, general Telegram, Twitter, etc.)
export const OTHER_SOURCES: SourceDefinition[] = [
  { id: "telegram_other", name: "Telegram (Other)", category: "media", enabled: true, icon: "💬", patterns: ["[tg @", "[tg@", "t.me/"] },
  { id: "reddit", name: "Reddit", category: "media", enabled: true, icon: "🔶", patterns: ["[reddit", "reddit.com", "r/iran", "r/newiran"] },
  { id: "twitter", name: "Twitter/X", category: "media", enabled: true, icon: "🐦", patterns: ["[@", "twitter.com", "x.com"] },
  { id: "rss_other", name: "RSS/News (Other)", category: "media", enabled: true, icon: "📰", patterns: ["[hrw]", "[amnesty]", "[reuters", "[al jazeera", "[dw ", "[voa "] },
  { id: "unknown", name: "Unknown Sources", category: "media", enabled: true, icon: "❓", patterns: [] },
];

// Helper function to check if an event matches a source
export function eventMatchesSource(eventTitle: string, sourceUrl: string | null, source: SourceDefinition): boolean {
  if (source.patterns.length === 0) return false; // Empty patterns = special case (unknown)
  const titleLower = eventTitle.toLowerCase();
  const urlLower = (sourceUrl || "").toLowerCase();
  return source.patterns.some(pattern => 
    titleLower.includes(pattern.toLowerCase()) || urlLower.includes(pattern.toLowerCase())
  );
}

// Helper function to get matching source ID for an event
export function getEventSourceId(eventTitle: string, sourceUrl: string | null): string {
  // Check media sources first (specific channels)
  for (const source of MEDIA_SOURCES) {
    if (eventMatchesSource(eventTitle, sourceUrl, source)) {
      return source.id;
    }
  }
  // Check OSINT sources
  for (const source of OSINT_SOURCES) {
    if (eventMatchesSource(eventTitle, sourceUrl, source)) {
      return source.id;
    }
  }
  // Check other sources (generic platform matches)
  for (const source of OTHER_SOURCES) {
    if (source.id !== "unknown" && eventMatchesSource(eventTitle, sourceUrl, source)) {
      return source.id;
    }
  }
  // Fallback to "unknown"
  return "unknown";
}

export interface ProtestEvent {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    id: number | string;  // Can be string for clusters (e.g., "cluster_123")
    title: string;
    description: string;
    intensity: number;
    verified: boolean;
    timestamp: string | null;
    source_url: string | null;
    media_url: string | null;
    media_type: "image" | "video" | "video_thumb" | null;
    event_type: EventType;
    source_platform: SourcePlatform | null;
    // Cluster properties
    cluster_count: number;
    is_cluster: boolean;
    type_breakdown?: Record<string, number>;
    event_ids?: number[];
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: ProtestEvent[];
  total_events?: number;
  clustered_points?: number;
  cluster_radius_km?: number;
}

export interface Stats {
  total_reports: number;
  verified_incidents: number;
  police_presence: number;
  protests: number;
  clashes: number;
  arrests: number;
  hours_window: number;
}

// ============================================================================
// AIRSPACE / NOTAM TYPES
// ============================================================================
export type AirspaceType = "airspace_restriction" | "airport_closure" | "hazard_notice" | "temporary_restriction" | "warning_area";

export interface AirspaceEvent {
  type: "Feature";
  geometry: {
    type: "Polygon" | "Point";
    coordinates: number[][] | number[][][];
  };
  properties: {
    id: number;
    notam_id: string | null;
    title: string;
    description: string;
    airspace_type: AirspaceType;
    ts_start: string | null;
    ts_end: string | null;
    is_permanent: boolean;
    lower_limit: number;
    upper_limit: number;
    radius_nm: number | null;
    fir: string | null;
    source: string;
  };
}

export interface AirspaceCollection {
  type: "FeatureCollection";
  features: AirspaceEvent[];
  count: number;
}

// Airspace type display configuration
export const AIRSPACE_TYPE_CONFIG: Record<AirspaceType, { label: string; color: string; fillColor: string }> = {
  airspace_restriction: { label: "Restricted Area", color: "#ff4444", fillColor: "rgba(255, 68, 68, 0.3)" },
  airport_closure: { label: "Airport Closed", color: "#ff8800", fillColor: "rgba(255, 136, 0, 0.3)" },
  hazard_notice: { label: "Hazard Notice", color: "#ffcc00", fillColor: "rgba(255, 204, 0, 0.3)" },
  temporary_restriction: { label: "Temp. Restriction", color: "#ff0088", fillColor: "rgba(255, 0, 136, 0.3)" },
  warning_area: { label: "Warning Area", color: "#8800ff", fillColor: "rgba(136, 0, 255, 0.3)" },
};


// ============================================================================
// INTERNET CONNECTIVITY TYPES
// ============================================================================
export type ConnectivityStatus = "normal" | "degraded" | "restricted" | "blackout" | "unknown";

export interface ProvinceConnectivity {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    id: string;
    name: string;
    name_fa: string;
    connectivity_score: number;
    status: ConnectivityStatus;
    population: number;
    updated_at: string;
  };
}

export interface ConnectivityCollection {
  type: "FeatureCollection";
  features: ProvinceConnectivity[];
  metadata: {
    national_score: number;
    national_status: ConnectivityStatus;
    updated_at: string;
    total_provinces: number;
  };
}

// Connectivity status display configuration
export const CONNECTIVITY_STATUS_CONFIG: Record<ConnectivityStatus, { 
  label: string; 
  color: string; 
  bgColor: string;
  icon: string;
  description: string;
}> = {
  normal: { 
    label: "Normal", 
    color: "#22c55e", 
    bgColor: "rgba(34, 197, 94, 0.3)",
    icon: "✅",
    description: "Full internet access"
  },
  degraded: { 
    label: "Degraded", 
    color: "#eab308", 
    bgColor: "rgba(234, 179, 8, 0.3)",
    icon: "⚠️",
    description: "Slow or intermittent connection"
  },
  restricted: { 
    label: "Restricted", 
    color: "#f97316", 
    bgColor: "rgba(249, 115, 22, 0.3)",
    icon: "🔒",
    description: "Major services blocked"
  },
  blackout: { 
    label: "Blackout", 
    color: "#ef4444", 
    bgColor: "rgba(239, 68, 68, 0.4)",
    icon: "🚫",
    description: "No internet access"
  },
  unknown: { 
    label: "Unknown", 
    color: "#6b7280", 
    bgColor: "rgba(107, 114, 128, 0.3)",
    icon: "❓",
    description: "Status unavailable"
  },
};

