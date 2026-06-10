"use client";

import { useRef, useState } from "react";
import { Save } from "lucide-react";
import { snapshotUrl, updateRoi } from "@/lib/api";
import type { Roi } from "@/lib/types";
import { DEFAULT_RECT_ROI } from "@/lib/types";
import { Button, ErrorBanner } from "@/components/ui";

type Props = {
  cameraId: number;
  initialRoi: Roi;
  onSaved: (roi: Roi) => void;
};

type Mode = "rect" | "poly";
type Point = { x: number; y: number };

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

// Edytor ROI rysowany na podglądzie snapshotu. Współrzędne znormalizowane 0..1,
// niezależne od rozmiaru obrazu — overlay SVG ma viewBox 0 0 1 1.
export default function RoiEditor({ cameraId, initialRoi, onSaved }: Props) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>("rect");
  const [roi, setRoi] = useState<Roi>(initialRoi);
  const [bust, setBust] = useState(() => 1);
  const [snapErr, setSnapErr] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Rysowanie prostokąta (przeciąganie).
  const dragStart = useRef<Point | null>(null);
  const [dragRect, setDragRect] = useState<Roi | null>(null);
  // Wielokąt w budowie.
  const [polyPoints, setPolyPoints] = useState<Point[]>([]);

  function toNorm(e: React.PointerEvent | React.MouseEvent): Point {
    const r = surfaceRef.current!.getBoundingClientRect();
    return {
      x: clamp01((e.clientX - r.left) / r.width),
      y: clamp01((e.clientY - r.top) / r.height),
    };
  }

  function rectFrom(a: Point, b: Point): Roi {
    return {
      shape: "rect",
      x: Math.min(a.x, b.x),
      y: Math.min(a.y, b.y),
      w: Math.abs(a.x - b.x),
      h: Math.abs(a.y - b.y),
    };
  }

  function onPointerDown(e: React.PointerEvent) {
    if (mode !== "rect") return;
    surfaceRef.current?.setPointerCapture(e.pointerId);
    dragStart.current = toNorm(e);
    setDragRect(null);
  }

  function onPointerMove(e: React.PointerEvent) {
    if (mode !== "rect" || !dragStart.current) return;
    setDragRect(rectFrom(dragStart.current, toNorm(e)));
  }

  function onPointerUp(e: React.PointerEvent) {
    if (mode !== "rect" || !dragStart.current) return;
    const rect = rectFrom(dragStart.current, toNorm(e));
    dragStart.current = null;
    setDragRect(null);
    if (rect.shape === "rect" && rect.w > 0.01 && rect.h > 0.01) setRoi(rect);
  }

  function onSurfaceClick(e: React.MouseEvent) {
    if (mode !== "poly") return;
    setPolyPoints((pts) => [...pts, toNorm(e)]);
  }

  function closePoly() {
    if (polyPoints.length < 3) return;
    setRoi({ shape: "poly", points: polyPoints.map((p) => [p.x, p.y]) });
    setPolyPoints([]);
  }

  function switchMode(m: Mode) {
    setMode(m);
    setPolyPoints([]);
    setDragRect(null);
    dragStart.current = null;
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await updateRoi(cameraId, roi);
      onSaved(roi);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zapisać ROI.");
    } finally {
      setSaving(false);
    }
  }

  // ROI pokazywany na overlayu: w trybie poly-w-budowie pokaż linię roboczą,
  // inaczej zapisany/narysowany ROI (z podglądem przeciągania).
  const shown: Roi | null = dragRect ?? roi;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">Tryb:</span>
        <Button variant={mode === "rect" ? "primary" : "ghost"} onClick={() => switchMode("rect")}>
          Prostokąt
        </Button>
        <Button variant={mode === "poly" ? "primary" : "ghost"} onClick={() => switchMode("poly")}>
          Wielokąt
        </Button>
        <Button variant="ghost" onClick={() => setRoi(DEFAULT_RECT_ROI)}>
          Cały kadr
        </Button>
        <Button variant="ghost" onClick={() => setBust((b) => b + 1)} title="Odśwież podgląd">
          Odśwież
        </Button>
      </div>

      <div
        ref={surfaceRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onClick={onSurfaceClick}
        className="relative aspect-video w-full max-w-lg cursor-crosshair touch-none select-none overflow-hidden rounded-lg border border-border bg-black/40"
      >
        {!snapErr ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={snapshotUrl(cameraId, bust)}
            alt="Podgląd kamery"
            className="pointer-events-none absolute inset-0 h-full w-full object-cover"
            onError={() => setSnapErr(true)}
          />
        ) : (
          <div className="absolute inset-0 grid place-items-center p-4 text-center text-xs text-fg-subtle">
            Brak podglądu (go2rtc niedostępny). ROI można narysować mimo to.
          </div>
        )}

        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
        >
          {shown?.shape === "rect" && (
            <rect
              x={shown.x}
              y={shown.y}
              width={shown.w}
              height={shown.h}
              fill="rgba(34,197,94,0.15)"
              stroke="#22c55e"
              strokeWidth={0.005}
            />
          )}
          {shown?.shape === "poly" && (
            <polygon
              points={shown.points.map((p) => `${p[0]},${p[1]}`).join(" ")}
              fill="rgba(34,197,94,0.15)"
              stroke="#22c55e"
              strokeWidth={0.005}
            />
          )}
          {mode === "poly" && polyPoints.length > 0 && (
            <>
              <polyline
                points={polyPoints.map((p) => `${p.x},${p.y}`).join(" ")}
                fill="none"
                stroke="#3b82f6"
                strokeWidth={0.005}
              />
              {polyPoints.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={0.008} fill="#3b82f6" />
              ))}
            </>
          )}
        </svg>
      </div>

      {mode === "rect" ? (
        <p className="text-xs text-fg-subtle">Przeciągnij na podglądzie, aby zaznaczyć prostokąt.</p>
      ) : (
        <div className="flex items-center gap-2">
          <p className="text-xs text-fg-subtle">
            Klikaj, aby dodać wierzchołki ({polyPoints.length}).
          </p>
          <Button variant="ghost" onClick={closePoly} disabled={polyPoints.length < 3}>
            Zamknij wielokąt
          </Button>
          {polyPoints.length > 0 && (
            <Button variant="ghost" onClick={() => setPolyPoints([])}>
              Cofnij
            </Button>
          )}
        </div>
      )}

      <ErrorBanner message={error} />

      <div>
        <Button onClick={save} disabled={saving}>
          <Save className="size-4" />
          Zapisz ROI
        </Button>
      </div>
    </div>
  );
}
