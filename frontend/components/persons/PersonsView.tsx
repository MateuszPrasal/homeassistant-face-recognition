"use client";

import { useCallback, useEffect, useState } from "react";
import { UserPlus } from "lucide-react";
import { ApiError, createPerson, listPersons } from "@/lib/api";
import type { Person } from "@/lib/types";
import { Button, ErrorBanner, Field, Spinner } from "@/components/ui";
import PersonCard from "./PersonCard";

export default function PersonsView() {
  const [persons, setPersons] = useState<Person[] | null>(null);
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setPersons(await listPersons());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Nie udało się wczytać osób.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setAdding(true);
    setError(null);
    try {
      await createPerson(trimmed);
      setName("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się dodać osoby.");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <form onSubmit={onAdd} className="flex items-end gap-2">
        <Field
          label="Nowa osoba"
          placeholder="Imię domownika"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="min-w-0 flex-1"
        />
        <Button type="submit" disabled={adding || !name.trim()}>
          <UserPlus className="size-4" />
          Dodaj
        </Button>
      </form>

      <ErrorBanner message={error} />

      {persons === null ? (
        <Spinner label="Wczytuję osoby…" />
      ) : persons.length === 0 ? (
        <p className="text-sm text-fg-subtle">Brak osób. Dodaj pierwszego domownika powyżej.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {persons.map((p) => (
            <li key={p.id}>
              <PersonCard person={p} onChanged={refresh} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
