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
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: ProtestEvent[];
}

