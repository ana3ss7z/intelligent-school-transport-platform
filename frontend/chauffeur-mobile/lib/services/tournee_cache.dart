import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';

/// Cache local de la dernière tournée connue, par (groupe, sens).
///
/// Raison d'être : la géométrie d'une tournée vient de MS5, injoignable hors
/// ligne. Or démarrer un trajet **sans** géométrie prive MS11 de sa référence et
/// désarme la détection de déviation (UC-8) — **sans aucune erreur visible**.
/// Le cache permet donc de démarrer hors ligne *avec* une tournée valide ; sans
/// cache, l'écran de tournée refuse le démarrage plutôt que de partir aveugle.
class TourneeCache {
  static String _key(int groupeId, String sens) =>
      'tournee_${groupeId}_${sens.toLowerCase()}';

  // Un cache qui lève est pire qu'un cache qui rate : ces deux méthodes
  // avalent leurs erreurs (stockage indisponible, quota, contenu corrompu) et
  // dégradent en « pas de cache », jamais en exception remontée à l'écran.

  Future<void> save(int groupeId, String sens, TourneePlan plan) async {
    if (!plan.hasGeometrie) return; // une tournée sans tracé n'a rien à cacher
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key(groupeId, sens), jsonEncode(plan.toJson()));
    } catch (_) {
      /* cache indisponible — sans effet sur le fonctionnement en ligne */
    }
  }

  Future<TourneePlan?> load(int groupeId, String sens) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key(groupeId, sens));
      if (raw == null || raw.isEmpty) return null;
      try {
        return TourneePlan.fromJson(
          Map<String, dynamic>.from(jsonDecode(raw) as Map),
        );
      } catch (_) {
        await prefs.remove(_key(groupeId, sens));
        return null;
      }
    } catch (_) {
      return null;
    }
  }
}
