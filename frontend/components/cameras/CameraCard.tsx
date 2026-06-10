"use client";

import { useState } from "react";
import { deleteCamera, updateCamera } from "@/lib/api";
import type { Camera } from "@/lib/types";
import { Button, ErrorBanner, Field } from "@/components/ui";
import RoiEditor from "./RoiEditor";

type Props = {
  camera: Camera;
  onChanged: () => void;
};

function roiLabel(c: Camera): string {
  if (c.roi.shape === "rect") {
    const full = c.roi.x === 0 && c.roi.y === 0 && c.roi.w === 1 && c.roi.h === 1;
    return full ? "cały kadr" : "prostokąt";
  }
  return `wielokąt (${c.roi.points.length})`;
}

export default function CameraCard({ camera, onChanged }: Props) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Lokalny stan edytowalnych pól (poza ROI — to robi RoiEditor).
  const [form, setForm] = useState({
    name: camera.name,
    source: camera.source,
    interval_seconds: String(camera.interval_seconds),
    cooldown_seconds: String(camera.cooldown_seconds),
    motion_threshold: String(camera.motion_threshold),
    enabled: camera.enabled,
  });

  async function saveSettings() {
    setSaving(true);
    setError(null);
    try {
      await updateCamera(camera.id, {
        name: form.name.trim(),
        source: form.source.trim(),
        interval_seconds: Number(form.interval_seconds),
        cooldown_seconds: Number(form.cooldown_seconds),
        motion_threshold: Number(form.motion_threshold),
        enabled: form.enabled,
      });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zapisać ustawień.");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    if (!confirm(`Usunąć kamerę „${camera.name}"?`)) return;
    await deleteCamera(camera.id);
    onChanged();
  }

  return (
    <div className="rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
      <div className="flex items-center justify-between gap-3 p-4">
        <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-2 text-left">
          <span className={`text-xs opacity-50 transition-transform ${open ? "rotate-90" : ""}`}>
            ▶
          </span>
          <span className="font-medium">{camera.name}</span>
          <span
            className={`size-2 rounded-full ${camera.enabled ? "bg-green-500" : "bg-gray-400"}`}
            title={camera.enabled ? "włączona" : "wyłączona"}
          />
          <span className="text-xs opacity-50">
            {camera.source} · ROI: {roiLabel(camera)}
          </span>
        </button>
        <Button variant="danger" onClick={onDelete}>
          Usuń
        </Button>
      </div>

      {open && (
        <div className="flex flex-col gap-5 border-t border-black/10 dark:border-white/10 p-4">
          <section>
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide opacity-50">
              Region detekcji (ROI)
            </h4>
            <RoiEditor cameraId={camera.id} initialRoi={camera.roi} onSaved={onChanged} />
          </section>

          <section className="flex flex-col gap-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide opacity-50">Ustawienia</h4>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field
                label="Nazwa"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <Field
                label="Źródło (stream go2rtc / URL)"
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
              />
              <Field
                label="Interwał (s)"
                type="number"
                step="0.5"
                min="0.5"
                value={form.interval_seconds}
                onChange={(e) => setForm({ ...form, interval_seconds: e.target.value })}
              />
              <Field
                label="Cooldown (s)"
                type="number"
                step="5"
                min="0"
                value={form.cooldown_seconds}
                onChange={(e) => setForm({ ...form, cooldown_seconds: e.target.value })}
              />
              <Field
                label="Próg ruchu (0–1)"
                hint="Frakcja zmienionych pikseli ROI uznawana za ruch"
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={form.motion_threshold}
                onChange={(e) => setForm({ ...form, motion_threshold: e.target.value })}
              />
              <label className="flex items-center gap-2 self-end text-sm">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                Włączona
              </label>
            </div>
            <ErrorBanner message={error} />
            <div>
              <Button onClick={saveSettings} disabled={saving}>
                Zapisz ustawienia
              </Button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
