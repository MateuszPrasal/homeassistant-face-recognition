// Post-build: zamiana absolutnych ścieżek assetów na względne w eksporcie Next.
//
// Po co: pod Ingress HA front ładuje się spod dynamicznego prefiksu
// /api/hassio_ingress/<token>/. Absolutne `/_next/...` rozwiązują się względem
// roota originu (czyli rdzenia HA, nie add-onu) → 404. Co gorsza, runtime
// turbopacka ma na sztywno `t="/_next/"` i tym prefiksuje doładowywane chunki —
// samo <base href> tego nie naprawi, bo ścieżki absolutne ignorują bazę.
//
// Rozwiązanie: robimy WSZYSTKIE odwołania względne (bez wiodącego `/`). Wtedy
// rozwiązują się względem <base href> wstrzykiwanego przez backend z nagłówka
// X-Ingress-Path (a bez Ingress — względem `/`, czyli bez zmian).
//
// Świadomie build-time, nie per-request: przepisywanie chunków JS przy każdym
// żądaniu zarżnęłoby RPi. Tu robimy to raz, na statycznym eksporcie.

import { readdir, readFile, writeFile, stat } from "node:fs/promises";
import { join, extname } from "node:path";

const OUT = process.argv[2] || "out";
const EXTS = new Set([".html", ".js", ".txt", ".css", ".json"]);

// Root-assety eksportu (public/) referowane absolutnie z wiodącym `/`.
const ROOT_ASSETS = ["favicon.ico", "file.svg", "globe.svg", "next.svg", "vercel.svg", "window.svg"];

async function* walk(dir) {
  for (const name of await readdir(dir)) {
    const p = join(dir, name);
    if ((await stat(p)).isDirectory()) yield* walk(p);
    else yield p;
  }
}

function relativize(text) {
  // `/_next/` → `_next/` (kryje też literał `t="/_next/"` w runtime turbopacka
  // oraz odwołania w danych RSC `\"/_next/...\"`). W tym eksporcie `/_next/`
  // zawsze znaczy „asset spod roota", więc zamiana globalna jest bezpieczna.
  let out = text.split("/_next/").join("_next/");
  // Root-assety: tylko gdy poprzedza je `"`, `'` lub `(` (kontekst URL-a),
  // żeby nie ruszać przypadkowych podciągów.
  for (const asset of ROOT_ASSETS) {
    out = out.replace(new RegExp('([("\'])\\/' + asset.replace(".", "\\."), "g"), "$1" + asset);
  }
  return out;
}

let changed = 0;
for await (const file of walk(OUT)) {
  if (!EXTS.has(extname(file))) continue;
  const before = await readFile(file, "utf8");
  const after = relativize(before);
  if (after !== before) {
    await writeFile(file, after);
    changed++;
  }
}
console.log(`relativize: przepisano ${changed} plik(ów) w ${OUT}/`);
