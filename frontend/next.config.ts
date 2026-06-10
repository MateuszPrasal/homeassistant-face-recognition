import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Statyczny eksport — bez runtime Node w produkcji (RAM na RPi).
  // Backend (FastAPI) serwuje wynikowy katalog `out/`.
  output: "export",

  // Pod Ingress każda trasa jako katalog z index.html lepiej się serwuje,
  // a względne ścieżki assetów łatwiej rozwiązać przez <base href>.
  trailingSlash: true,

  // Eksport statyczny nie ma serwera do optymalizacji obrazów.
  images: { unoptimized: true },

  // UWAGA (Ingress): prefiks ścieżki jest dynamiczny (/api/hassio_ingress/<token>/),
  // więc basePath (build-time) nie zadziała. Ścieżki assetów trzymamy względne,
  // a bazę poda <base href> wstrzykiwany przez backend z nagłówka X-Ingress-Path.
  // Konfiguracja domknięta w fazie pakowania add-onu.
};

export default nextConfig;
