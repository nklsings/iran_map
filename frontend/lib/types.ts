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
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: ProtestEvent[];
}

