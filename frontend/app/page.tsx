"use client";

import { useState } from "react";
import { ScanFace, Users, Camera, Activity, type LucideIcon } from "lucide-react";
import PersonsView from "@/components/persons/PersonsView";
import CamerasView from "@/components/cameras/CamerasView";
import EventsView from "@/components/events/EventsView";

type Tab = "persons" | "cameras" | "events";

const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: "persons", label: "Osoby", icon: Users },
  { id: "cameras", label: "Kamery", icon: Camera },
  { id: "events", label: "Zdarzenia", icon: Activity },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("persons");

  return (
    <div className="flex-1">
      <header className="border-b border-border bg-surface/40 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center gap-3 px-4 py-4">
          <span className="grid size-9 place-items-center rounded-lg bg-accent/10 text-accent ring-1 ring-accent/25">
            <ScanFace className="size-5" />
          </span>
          <div className="min-w-0">
            <h1 className="text-base font-semibold leading-tight">Rozpoznawanie twarzy</h1>
            <p className="text-xs text-fg-muted">Panel domowników i kamer · Home Assistant</p>
          </div>
        </div>

        <nav className="mx-auto flex w-full max-w-3xl gap-1 px-2">
          {TABS.map((t) => {
            const active = tab === t.id;
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
                  active
                    ? "border-accent text-accent"
                    : "border-transparent text-fg-muted hover:text-fg"
                }`}
              >
                <Icon className="size-4" />
                {t.label}
              </button>
            );
          })}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 py-6">
        {tab === "persons" && <PersonsView />}
        {tab === "cameras" && <CamerasView />}
        {tab === "events" && <EventsView />}
      </main>
    </div>
  );
}
