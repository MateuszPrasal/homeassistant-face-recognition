// Typy zwierciedlające schematy API (backend/app/schemas.py, roi.py).

export type RectRoi = {
  shape: "rect";
  x: number;
  y: number;
  w: number;
  h: number;
};

export type PolyRoi = {
  shape: "poly";
  points: [number, number][];
};

export type Roi = RectRoi | PolyRoi;

export type Camera = {
  id: number;
  name: string;
  source: string;
  roi: Roi;
  interval_seconds: number;
  cooldown_seconds: number;
  motion_threshold: number;
  enabled: boolean;
  created_at: string;
};

// Pola edytowalne w formularzu (POST/PATCH).
export type CameraInput = {
  name: string;
  source: string;
  roi: Roi;
  interval_seconds: number;
  cooldown_seconds: number;
  motion_threshold: number;
  enabled: boolean;
};

export type Person = {
  id: number;
  name: string;
  created_at: string;
  face_count: number;
};

export type Face = {
  id: number;
  person_id: number;
  created_at: string;
};

export type DetectedFace = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  score: number;
};

export type DetectResult = {
  width: number;
  height: number;
  faces: DetectedFace[];
};

export const DEFAULT_RECT_ROI: RectRoi = { shape: "rect", x: 0, y: 0, w: 1, h: 1 };
