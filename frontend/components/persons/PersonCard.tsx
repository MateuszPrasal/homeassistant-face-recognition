"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Trash2, X } from "lucide-react";
import { deleteFace, deletePerson, listFaces } from "@/lib/api";
import type { Face, Person } from "@/lib/types";
import { Badge, Button, Spinner } from "@/components/ui";
import FaceEnroll from "./FaceEnroll";

type Props = {
  person: Person;
  onChanged: () => void;
};

export default function PersonCard({ person, onChanged }: Props) {
  const [open, setOpen] = useState(false);
  const [faces, setFaces] = useState<Face[] | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setFaces(await listFaces(person.id));
    } finally {
      setLoading(false);
    }
    onChanged(); // odśwież face_count w liście
  }, [person.id, onChanged]);

  useEffect(() => {
    if (open && faces === null) void refresh();
  }, [open, faces, refresh]);

  async function onDeletePerson() {
    if (!confirm(`Usunąć osobę „${person.name}" i wszystkie jej twarze?`)) return;
    await deletePerson(person.id);
    onChanged();
  }

  async function onDeleteFace(id: number) {
    await deleteFace(id);
    await refresh();
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between gap-3 p-4">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex min-w-0 items-center gap-2 text-left"
        >
          <ChevronRight
            className={`size-4 shrink-0 text-fg-subtle transition-transform ${open ? "rotate-90" : ""}`}
          />
          <span className="truncate font-medium">{person.name}</span>
          <Badge tone="accent">
            {person.face_count} {person.face_count === 1 ? "twarz" : "twarzy"}
          </Badge>
        </button>
        <Button variant="danger" onClick={onDeletePerson}>
          <Trash2 className="size-4" />
          Usuń
        </Button>
      </div>

      {open && (
        <div className="flex flex-col gap-4 border-t border-border p-4">
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
              Zapisane twarze
            </h4>
            {loading && faces === null ? (
              <Spinner />
            ) : faces && faces.length > 0 ? (
              <ul className="flex flex-wrap gap-2">
                {faces.map((f) => (
                  <li
                    key={f.id}
                    className="flex items-center gap-2 rounded-md bg-surface-2 px-2.5 py-1 text-sm"
                  >
                    <span className="font-mono text-fg-muted">#{f.id}</span>
                    <button
                      onClick={() => onDeleteFace(f.id)}
                      className="text-danger transition-opacity hover:opacity-70"
                      title="Usuń twarz"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-fg-subtle">Brak twarzy — dodaj zdjęcie poniżej.</p>
            )}
          </section>

          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
              Dodaj twarz ze zdjęcia
            </h4>
            <FaceEnroll personId={person.id} onEnrolled={refresh} />
          </section>
        </div>
      )}
    </div>
  );
}
