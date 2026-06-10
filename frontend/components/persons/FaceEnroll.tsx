"use client";

import { useRef, useState } from "react";
import { ApiError, detectFace, enrollFace } from "@/lib/api";
import type { DetectResult } from "@/lib/types";
import { Button, ErrorBanner } from "@/components/ui";

type Props = {
  personId: number;
  onEnrolled: () => void;
};

// Wybór zdjęcia → podgląd detekcji (ramka) → zapis embeddingu.
// Zapis dozwolony tylko, gdy na zdjęciu jest dokładnie jedna twarz.
export default function FaceEnroll({ personId, onEnrolled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [detect, setDetect] = useState<DetectResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview(null);
    setDetect(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function onPick(picked: File) {
    if (preview) URL.revokeObjectURL(preview);
    setFile(picked);
    setPreview(URL.createObjectURL(picked));
    setDetect(null);
    setError(null);
    setBusy(true);
    try {
      setDetect(await detectFace(picked));
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 503
          ? "Modele ML niezaładowane — kaskada wyłączona lub jeszcze się ładuje."
          : e instanceof Error
            ? e.message
            : "Nie udało się wykryć twarzy.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await enrollFace(personId, file);
      reset();
      onEnrolled();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zapisać twarzy.");
    } finally {
      setBusy(false);
    }
  }

  const faceCount = detect?.faces.length ?? 0;
  const canSave = !busy && faceCount === 1;

  return (
    <div className="flex flex-col gap-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
        }}
        className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-black/10 dark:file:bg-white/15 file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-black/20 dark:hover:file:bg-white/25"
      />

      {preview && (
        <div className="relative w-full max-w-sm overflow-hidden rounded-lg border border-black/10 dark:border-white/10">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt="Podgląd" className="block w-full" />
          {detect && (
            <svg
              viewBox={`0 0 ${detect.width} ${detect.height}`}
              preserveAspectRatio="none"
              className="absolute inset-0 h-full w-full"
            >
              {detect.faces.map((f, i) => (
                <g key={i}>
                  <rect
                    x={f.x1}
                    y={f.y1}
                    width={f.x2 - f.x1}
                    height={f.y2 - f.y1}
                    fill="none"
                    stroke={faceCount === 1 ? "#22c55e" : "#ef4444"}
                    strokeWidth={Math.max(detect.width, detect.height) / 200}
                  />
                </g>
              ))}
            </svg>
          )}
        </div>
      )}

      {busy && !detect && <span className="text-sm opacity-60">Analizuję zdjęcie…</span>}

      {detect && (
        <p className="text-sm opacity-70">
          {faceCount === 0 && "Nie wykryto twarzy — wybierz inne zdjęcie."}
          {faceCount === 1 && `Wykryto twarz (pewność ${detect.faces[0].score}).`}
          {faceCount > 1 && `Wykryto ${faceCount} twarze — potrzebne zdjęcie z jedną osobą.`}
        </p>
      )}

      <ErrorBanner message={error} />

      <div className="flex gap-2">
        <Button onClick={onSave} disabled={!canSave}>
          Zapisz twarz
        </Button>
        {file && (
          <Button variant="ghost" onClick={reset} disabled={busy}>
            Wyczyść
          </Button>
        )}
      </div>
    </div>
  );
}
