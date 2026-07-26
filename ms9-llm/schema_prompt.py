"""Schéma de base CURÉ (colonnes sûres uniquement) injecté dans le prompt NL2SQL admin."""

SCHEMA = """Base PostgreSQL « transport_scolaire ». Tables et colonnes DISPONIBLES (n'utilise QUE celles-ci) :

utilisateurs(id, nom, email, role, telephone)
  - role ∈ {ADMIN, CHAUFFEUR, PARENT}
bus(id, matricule, capacite, statut, chauffeur_id, latitude, longitude)
  - statut ∈ {ACTIF, INACTIF, EN_PANNE}
eleves(id, nom, prenom, parent_id, bus_id, groupe_id, statut_presence, ordre_passage, latitude, longitude)
  - statut_presence : boolean (true = à bord)
incidents(id, bus_id, type, statut, description, signale_par, date_signalement, date_resolution, notes_resolution)
  - type ∈ {ACCIDENT, PANNE, RETARD, ABSENCE_CHAUFFEUR, ROUTE_BLOQUEE, AUTRE}
  - statut ∈ {SIGNALE, CONFIRME, EN_TRAITEMENT, RESOLU}
trajets(id, bus_id, chauffeur_id, sens, statut, heure_debut, heure_fin, groupe_id)
  - sens ∈ {MATIN, SOIR} ; statut ∈ {EN_COURS, TERMINE}
notifications(id, type, statut_envoi, parent_id, titre, message, source_id, source_type, date_envoi, erreur_fcm)
  - statut_envoi ∈ {EN_ATTENTE, ENVOYE, ECHEC}
messages(id, expediteur_id, expediteur_nom, expediteur_role, destinataire_id, destinataire_role, conversation_chauffeur_id, diffusion, lu, date_envoi)
positions_gps(id, cible_type, cible_id, latitude, longitude, vitesse, cap, horodatage)
  - cible_type ∈ {BUS, ELEVE}

Relations (jointures logiques, pas de FK physique) :
  eleves.parent_id = utilisateurs.id (role PARENT)
  eleves.bus_id = bus.id ; eleves.groupe_id = groupe/bus
  bus.chauffeur_id = utilisateurs.id (role CHAUFFEUR)
  incidents.bus_id = bus.id ; incidents.signale_par = utilisateurs.id
  trajets.bus_id = bus.id ; trajets.chauffeur_id = utilisateurs.id
  notifications.parent_id = utilisateurs.id
  positions_gps.cible_id = bus.id (si cible_type='BUS') ou eleves.id (si cible_type='ELEVE')

Règles SQL STRICTES :
  - PostgreSQL uniquement. Dates relatives : NOW() - INTERVAL '7 days', date_trunc('week', ...), CURRENT_DATE.
  - N'utilise JAMAIS « SELECT * » : liste explicitement les colonnes.
  - Toujours une seule requête SELECT (jamais INSERT/UPDATE/DELETE/DDL).
  - Termine par un LIMIT raisonnable.
  - Utilise EXACTEMENT les noms de tables/colonnes ci-dessus (rien d'autre n'existe/n'est accessible)."""
