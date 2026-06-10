// Klient REST API backendu.
//
// Ingress: front jedzie pod dynamicznym prefiksem /api/hassio_ingress/<token>/,
// więc ścieżki MUSZĄ być WZGLĘDNE (bez wiodącego "/"). Przeglądarka rozwiązuje
// je względem <base href> wstrzykiwanego przez backend (Faza 5). Serwowany prosto
// z FastAPI (na "/") też działa — "api/persons" → "/api/persons".
//
// Dev: Next na :3000 a backend na :8099. Ustaw NEXT_PUBLIC_API_BASE=http://localhost:8099
// (i FACE_CORS_ORIGINS=http://localhost:3000 po stronie backendu).

import type {
  Camera,
  CameraInput,
  DetectResult,
  Face,
  Person,
  Roi,
} from "./types";

const BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  const clean = path.replace(/^\/+/, "");
  return BASE ? `${BASE}/api/${clean}` : `api/${clean}`;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    // brak JSON-a — zostaje status
  }
  return `Błąd ${res.status}`;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), init);
  if (!res.ok) throw new ApiError(res.status, await detail(res));
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export { ApiError };

// --- Osoby ---

export const listPersons = () => req<Person[]>("persons");

export const createPerson = (name: string) =>
  req<Person>("persons", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

export const deletePerson = (id: number) =>
  req<void>(`persons/${id}`, { method: "DELETE" });

export const listFaces = (personId: number) =>
  req<Face[]>(`persons/${personId}/faces`);

export const deleteFace = (faceId: number) =>
  req<void>(`faces/${faceId}`, { method: "DELETE" });

export function detectFace(file: File): Promise<DetectResult> {
  const form = new FormData();
  form.append("file", file);
  return req<DetectResult>("detect", { method: "POST", body: form });
}

export function enrollFace(
  personId: number,
  file: File,
): Promise<{ face_id: number; detection_score: number }> {
  const form = new FormData();
  form.append("file", file);
  return req(`persons/${personId}/faces`, { method: "POST", body: form });
}

// --- Kamery ---

export const listCameras = () => req<Camera[]>("cameras");

export const createCamera = (data: CameraInput) =>
  req<Camera>("cameras", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export const updateCamera = (id: number, data: Partial<CameraInput>) =>
  req<Camera>(`cameras/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export const updateRoi = (id: number, roi: Roi) =>
  updateCamera(id, { roi });

export const deleteCamera = (id: number) =>
  req<void>(`cameras/${id}`, { method: "DELETE" });

// URL snapshotu (do <img src>). Cache-bust przez znacznik czasu.
export const snapshotUrl = (id: number, bust?: number) =>
  apiUrl(`cameras/${id}/snapshot`) + (bust ? `?t=${bust}` : "");
