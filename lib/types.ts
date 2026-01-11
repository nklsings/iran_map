// Event type constants
export type EventType = "protest" | "police_presence" | "strike" | "clash" | "arrest";
export type SourcePlatform = "telegram" | "reddit" | "instagram" | "youtube" | "rss" | "twitter" | "crowdsourced";

export interface ProtestEvent {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    id: number;
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
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: ProtestEvent[];
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

