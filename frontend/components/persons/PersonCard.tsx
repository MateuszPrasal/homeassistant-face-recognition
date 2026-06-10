"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteFace, deletePerson, listFaces } from "@/lib/api";
import type { Face, Person } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
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
    <div className="rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
      <div className="flex items-center justify-between gap-3 p-4">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-left"
        >
          <span className={`text-xs opacity-50 transition-transform ${open ? "rotate-90" : ""}`}>
            ▶
          </span>
          <span className="font-medium">{person.name}</span>
          <span className="rounded-full bg-black/10 dark:bg-white/15 px-2 py-0.5 text-xs opacity-80">
            {person.face_count} {person.face_count === 1 ? "twarz" : "twarzy"}
          </span>
        </button>
        <Button variant="danger" onClick={onDeletePerson}>
          Usuń
        </Button>
      </div>

      {open && (
        <div className="flex flex-col gap-4 border-t border-black/10 dark:border-white/10 p-4">
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide opacity-50">
              Zapisane twarze
            </h4>
            {loading && faces === null ? (
              <Spinner />
            ) : faces && faces.length > 0 ? (
              <ul className="flex flex-wrap gap-2">
                {faces.map((f) => (
                  <li
                    key={f.id}
                    className="flex items-center gap-2 rounded-md bg-black/5 dark:bg-white/10 px-2.5 py-1 text-sm"
                  >
                    <span className="opacity-70">#{f.id}</span>
                    <button
                      onClick={() => onDeleteFace(f.id)}
                      className="text-red-600 dark:text-red-400 hover:opacity-70"
                      title="Usuń twarz"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm opacity-50">Brak twarzy — dodaj zdjęcie poniżej.</p>
            )}
          </section>

          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide opacity-50">
              Dodaj twarz ze zdjęcia
            </h4>
            <FaceEnroll personId={person.id} onEnrolled={refresh} />
          </section>
        </div>
      )}
    </div>
  );
}
