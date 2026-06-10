"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, createCamera, listCameras } from "@/lib/api";
import type { Camera } from "@/lib/types";
import { DEFAULT_RECT_ROI } from "@/lib/types";
import { Button, Card, ErrorBanner, Field, Spinner } from "@/components/ui";
import CameraCard from "./CameraCard";

const EMPTY = { name: "", source: "" };

export default function CamerasView() {
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setCameras(await listCameras());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Nie udało się wczytać kamer.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.source.trim()) return;
    setAdding(true);
    setError(null);
    try {
      // ROI domyślnie cały kadr — user dorysowuje w edytorze po dodaniu.
      await createCamera({
        name: form.name.trim(),
        source: form.source.trim(),
        roi: DEFAULT_RECT_ROI,
        interval_seconds: 3,
        cooldown_seconds: 45,
        motion_threshold: 0.02,
        enabled: true,
      });
      setForm(EMPTY);
      setShowForm(false);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się dodać kamery.");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold opacity-70">Kamery</h2>
        <Button variant="ghost" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Anuluj" : "Dodaj kamerę"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <form onSubmit={onAdd} className="flex flex-col gap-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field
                label="Nazwa"
                placeholder="np. Wejście"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <Field
                label="Źródło (stream go2rtc / URL snapshotu)"
                placeholder="front_door"
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
              />
            </div>
            <p className="text-xs opacity-50">
              ROI i pozostałe parametry ustawisz po dodaniu, rozwijając kamerę.
            </p>
            <div>
              <Button type="submit" disabled={adding || !form.name.trim() || !form.source.trim()}>
                Dodaj
              </Button>
            </div>
          </form>
        </Card>
      )}

      <ErrorBanner message={error} />

      {cameras === null ? (
        <Spinner label="Wczytuję kamery…" />
      ) : cameras.length === 0 ? (
        <p className="text-sm opacity-50">Brak kamer. Dodaj pierwszą powyżej.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {cameras.map((c) => (
            <li key={c.id}>
              <CameraCard camera={c} onChanged={refresh} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
