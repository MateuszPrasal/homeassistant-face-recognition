"use client";

import { useState } from "react";
import PersonsView from "@/components/persons/PersonsView";
import CamerasView from "@/components/cameras/CamerasView";

type Tab = "persons" | "cameras";

const TABS: { id: Tab; label: string }[] = [
  { id: "persons", label: "Osoby" },
  { id: "cameras", label: "Kamery" },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("persons");

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Rozpoznawanie twarzy</h1>
        <p className="text-sm opacity-60">Panel domowników i kamer (Home Assistant)</p>
      </header>

      <nav className="mb-6 flex gap-1 border-b border-black/10 dark:border-white/10">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent opacity-60 hover:opacity-100"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "persons" ? <PersonsView /> : <CamerasView />}
    </main>
  );
}
