-- =====================================================================
-- MS9 Phase B — Rôle Postgres READ-ONLY pour l'assistant NL2SQL admin
-- =====================================================================
-- À exécuter UNE fois par un superuser (transport_user l'est) :
--   docker exec -i transport_postgres psql -U transport_user -d transport_scolaire \
--     -f - < ms9-llm/sql/create_readonly_role.sql
--
-- Le mot de passe DOIT correspondre à DB_RO_PASSWORD dans ms9-llm/.env.
-- Sécurité : lecture seule stricte + grants AU NIVEAU COLONNE (aucune colonne sensible :
--   mot_de_passe, fcm_token, messages.contenu, trajets.geometrie ; pas de device_tokens/PostGIS).
-- Idempotent (ré-exécutable).
-- =====================================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ms9_readonly') THEN
    CREATE ROLE ms9_readonly LOGIN PASSWORD 'Ms9ReadOnly_2026!';
  ELSE
    ALTER ROLE ms9_readonly LOGIN PASSWORD 'Ms9ReadOnly_2026!';
  END IF;
END $$;

-- Lecture seule + garde-fous de session
ALTER ROLE ms9_readonly SET default_transaction_read_only = on;
ALTER ROLE ms9_readonly SET statement_timeout = '5000ms';
ALTER ROLE ms9_readonly SET idle_in_transaction_session_timeout = '10000ms';

GRANT CONNECT ON DATABASE transport_scolaire TO ms9_readonly;
GRANT USAGE ON SCHEMA public TO ms9_readonly;

-- Repartir d'une base propre (au cas où des grants existeraient déjà)
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ms9_readonly;

-- Tables SANS colonne sensible → SELECT complet
GRANT SELECT ON bus, eleves, incidents, positions_gps TO ms9_readonly;

-- Tables AVEC colonne sensible → SELECT au niveau colonne (colonnes sûres uniquement)
GRANT SELECT (id, nom, email, role, telephone) ON utilisateurs TO ms9_readonly;                       -- exclut mot_de_passe
GRANT SELECT (id, bus_id, chauffeur_id, sens, statut, heure_debut, heure_fin, groupe_id) ON trajets TO ms9_readonly;  -- exclut geometrie
GRANT SELECT (id, type, statut_envoi, parent_id, titre, message, source_id, source_type, date_envoi, erreur_fcm) ON notifications TO ms9_readonly;  -- exclut fcm_token
GRANT SELECT (id, expediteur_id, expediteur_nom, expediteur_role, destinataire_id, destinataire_role, conversation_chauffeur_id, diffusion, lu, date_envoi) ON messages TO ms9_readonly;  -- exclut contenu

-- device_tokens : AUCUN accès (tokens FCM). PostGIS (spatial_ref_sys, *_columns) : non accordé.
