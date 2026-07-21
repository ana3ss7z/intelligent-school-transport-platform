import { useEffect, useRef, useState } from "react";
import { GraduationCap, Bus as BusIcon, Clock } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useMyChildren } from "../hooks/useMyChildren";
import { useGpsSocket } from "../hooks/useGpsSocket";
import { getTrajetActifBus, predictEta } from "../api/endpoints";
import type { Trajet } from "../api/types";
import { Panel, Stat, StatusChip, Spinner, SectionTitle } from "../components/ui";
import { EmptyState, ErrorState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

const ECOLE = { lat: 33.893, lng: -5.5455 };
const statutTone = (s?: string) => (s === "ACTIF" ? "ok" : s === "EN_PANNE" ? "alert" : "neutral");

export function ParentHome() {
  const { user } = useAuth();
  const { enfants, busById, busIds, loading, error, refetch } = useMyChildren();
  const { positions } = useGpsSocket(true);

  // Trajet EN_COURS par bus (null = pas démarré) — rafraîchi pour capter démarrage/fin
  const [trajets, setTrajets] = useState<Record<number, Trajet | null>>({});
  const idsKey = busIds.join(",");
  useEffect(() => {
    if (busIds.length === 0) return;
    let alive = true;
    const charger = async () => {
      const entries = await Promise.all(busIds.map(async (id) => {
        try { return [id, await getTrajetActifBus(id)] as const; }
        catch { return [id, null] as const; }
      }));
      if (alive) setTrajets(Object.fromEntries(entries));
    };
    charger();
    const t = setInterval(charger, 15000);
    return () => { alive = false; clearInterval(t); };
  }, [idsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // ETA par enfant vers la destination selon le sens (école le matin, domicile le soir) — SI trajet démarré
  const [etas, setEtas] = useState<Record<number, number>>({});
  const posRef = useRef(positions);
  posRef.current = positions;
  useEffect(() => {
    let alive = true;
    const compute = async () => {
      const res = await Promise.all(enfants.map(async (e) => {
        const busId = e.busId;
        const trajet = busId != null ? trajets[busId] : null;
        if (busId == null || !trajet) return [e.id, null] as const;
        const bus = busById.get(busId);
        const live = posRef.current[busId];
        const lat = live?.latitude ?? bus?.latitude;
        const lng = live?.longitude ?? bus?.longitude;
        if (lat == null || lng == null) return [e.id, null] as const;
        const soir = trajet.sens === "SOIR";
        const dest = soir ? { lat: e.latitude, lng: e.longitude } : ECOLE;
        try {
          const r = await predictEta({ bus_lat: lat, bus_lng: lng, dest_lat: dest.lat, dest_lng: dest.lng, moment: soir ? "soir" : "matin" });
          return [e.id, r.eta_minutes] as const;
        } catch { return [e.id, null] as const; }
      }));
      if (alive) setEtas(Object.fromEntries(res.filter((x): x is readonly [number, number] => x[1] != null)));
    };
    compute();
    const t = setInterval(compute, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [enfants, trajets, busById]);

  if (loading) return <Spinner label="Chargement de vos enfants…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const aBord = enfants.filter((e) => e.statutPresence).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Mon espace</h1>
        <p className="text-ink-soft text-sm">Bonjour {user?.nom} — suivi de vos enfants.</p>
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-3">
        <Stat label="Mes enfants" value={enfants.length} tone="route" />
        <Stat label="À bord" value={aBord} tone="ok" hint="actuellement dans le bus" />
        <Stat label="Bus concernés" value={new Set(enfants.map((e) => e.busId).filter(Boolean)).size} tone="line2" />
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${enfants.length} enfant(s)`}>Mes enfants</SectionTitle>
        {enfants.length === 0 ? (
          <EmptyState message="Aucun enfant rattaché à votre compte. Contactez l'administration." icon={<GraduationCap size={22} />} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {enfants.map((e) => {
              const bus = e.busId != null ? busById.get(e.busId) : undefined;
              const trajet = e.busId != null ? trajets[e.busId] : null;
              const eta = etas[e.id];
              const soir = trajet?.sens === "SOIR";
              return (
                <div key={e.id} className="rounded-lg border border-line p-3">
                  <div className="flex items-center gap-2.5">
                    <span className="grid place-items-center size-9 rounded-lg text-white shrink-0"
                      style={{ background: lineColor(e.groupeId ?? e.id) }}>
                      <GraduationCap size={18} />
                    </span>
                    <div className="min-w-0">
                      <div className="font-medium truncate">{e.prenom} {e.nom}</div>
                      <div className="text-[11px] text-ink-soft">
                        {e.groupeId != null ? `Groupe ${e.groupeId}` : "Sans groupe"}
                      </div>
                    </div>
                    <StatusChip tone={e.statutPresence ? "ok" : "neutral"}>
                      {e.statutPresence ? "à bord" : "pas à bord"}
                    </StatusChip>
                  </div>

                  <div className="mt-2 pt-2 border-t border-line/60 flex items-center gap-2 text-sm text-ink-soft">
                    <BusIcon size={15} />
                    {bus ? (
                      <>
                        <span className="tabular">{bus.matricule}</span>
                        <StatusChip tone={statutTone(bus.statut)}>{bus.statut}</StatusChip>
                      </>
                    ) : <span>Aucun bus assigné</span>}
                  </div>

                  {/* Compte à rebours — uniquement si un trajet est démarré */}
                  {trajet ? (
                    <div className="mt-2 flex items-center gap-2 rounded-lg px-2.5 py-2"
                      style={{ background: "var(--panel-2)" }}>
                      <Clock size={16} className="text-route shrink-0" />
                      {eta != null ? (
                        <span className="text-sm">
                          Le bus arrive dans <span className="font-semibold tabular">~{Math.round(eta)} min</span>{" "}
                          <span className="text-ink-soft">{soir ? "chez vous" : "à l'école"}</span>
                        </span>
                      ) : (
                        <span className="text-sm text-ink-soft">Trajet {soir ? "du soir" : "du matin"} en cours — calcul de l'arrivée…</span>
                      )}
                    </div>
                  ) : (
                    <div className="mt-2 text-[11px] text-ink-soft">Aucun trajet en cours.</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
