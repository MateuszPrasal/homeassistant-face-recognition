"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CircleCheck,
  CircleHelp,
  RefreshCw,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import {
  ApiError,
  detectionSnapshotUrl,
  listCameras,
  listDetections,
} from "@/lib/api";
import type { Camera, Detection, Outcome } from "@/lib/types";
import { Badge, Button, Card, ErrorBanner, Select, Spinner } from "@/components/ui";

type Tone = "accent" | "danger" | "warn" | "muted";

const OUTCOME: Record<Outcome, { label: string; tone: Tone; icon: LucideIcon }> = {
  ok: { label: "OK", tone: "accent", icon: CircleCheck },
  unknown_face: { label: "Nieznana twarz", tone: "danger", icon: TriangleAlert },
  person_no_face: { label: "Osoba bez twarzy", tone: "warn", icon: CircleHelp },
};

function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const o = OUTCOME[outcome];
  if (!o) return <Badge tone="muted">{outcome}</Badge>;
  const Icon = o.icon;
  return (
    <Badge tone={o.tone}>
      <Icon className="size-3.5" />
      {o.label}
    </Badge>
  );
}

// "2026-06-10T12:34:56" (UTC z SQLite) → lokalny, czytelny zapis.
function formatTime(iso: string): string {
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function EventsView() {
  const [rows, setRows] = useState<Detection[] | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [filter, setFilter] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listDetections(
        filter != null ? { limit: 100, cameraId: filter } : { limit: 100 },
      );
      setRows(list);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Nie udało się wczytać zdarzeń.");
    }
  }, [filter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Mapa id→nazwa kamery (do etykiet); osobny strzał, nie blokuje listy.
  useEffect(() => {
    listCameras()
      .then(setCameras)
      .catch(() => setCameras([]));
  }, []);

  const cameraName = (id: number) =>
    cameras.find((c) => c.id === id)?.name ?? `Kamera ${id}`;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">Zdarzenia</h2>
        <div className="flex items-center gap-2">
          <Select
            value={filter ?? ""}
            onChange={(e) => setFilter(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Wszystkie kamery</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Button variant="ghost" onClick={() => void refresh()}>
            <RefreshCw className="size-4" />
            Odśwież
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} />

      {rows === null ? (
        <Spinner label="Wczytuję zdarzenia…" />
      ) : rows.length === 0 ? (
        <p className="text-sm text-fg-subtle">
          Brak zdarzeń. Pojawią się, gdy w ROI wykryta zostanie osoba.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((d) => (
            <li key={d.id}>
              <Card className="flex items-center gap-3 p-3">
                {d.has_snapshot ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={detectionSnapshotUrl(d.id)}
                    alt="snapshot"
                    className="size-14 shrink-0 rounded-md border border-border object-cover"
                  />
                ) : (
                  <div className="flex size-14 shrink-0 items-center justify-center rounded-md bg-surface-2 text-xs text-fg-subtle">
                    —
                  </div>
                )}
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <OutcomeBadge outcome={d.outcome} />
                    {d.matched_name && (
                      <span className="truncate text-sm font-medium">{d.matched_name}</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-3 text-xs text-fg-muted">
                    <span>{formatTime(d.created_at)}</span>
                    <span>{cameraName(d.camera_id)}</span>
                    <span className="font-mono">score {d.score.toFixed(2)}</span>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
