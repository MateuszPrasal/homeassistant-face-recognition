export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-semibold">Rozpoznawanie twarzy</h1>
        <p className="mt-3 text-sm opacity-70">
          Panel zarządzania domownikami i kamerami. Szkielet — Faza 0.
        </p>
        <p className="mt-6 text-xs opacity-50">
          Serwis działa. Kolejne fazy: akwizycja obrazu, kaskada osoba→twarz, UI.
        </p>
      </div>
    </main>
  );
}
