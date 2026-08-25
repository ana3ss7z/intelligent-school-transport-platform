import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../config/env.dart';

/// Paramètres applicatifs servis par MS13.
/// =======================================
///
/// Avant MS13, les coordonnées de l'école et les intervalles de rafraîchissement étaient des
/// constantes compilées dans [Env] : les changer imposait de recompiler et de redéployer les
/// deux applications. Elles sont maintenant lues sur le serveur au démarrage.
///
/// Pourquoi passer par [Env] plutôt que par un fournisseur Riverpod dans chaque écran
/// --------------------------------------------------------------------------------
/// Ces valeurs sont lues depuis une vingtaine d'endroits, dont plusieurs `initState`. Les
/// remplacer une par une aurait touché autant d'écrans d'applications déjà livrées et
/// couvertes par leurs tests. En alimentant [Env] à la place, aucun site d'appel ne change :
/// `Env.ecoleLat` continue de fonctionner, mais renvoie désormais la valeur du serveur.
///
/// Repli hors ligne
/// ----------------
/// Trois niveaux, dans cet ordre : la réponse du serveur, la dernière réponse mise en cache
/// dans `shared_preferences`, puis les valeurs compilées d'origine. Une application de
/// transport scolaire doit démarrer dans un parking souterrain ; la configuration ne peut
/// pas être une dépendance dure.
///
/// `shared_preferences` est déjà une dépendance des deux applications, et surtout elle
/// **ne tire pas `path_provider`** — donc elle reste à l'écart du conflit `jni`/AGP 9 qui
/// impose d'épingler `path_provider_android`.
///
/// Limite assumée
/// --------------
/// Un `Timer.periodic` construit dans un `initState` conserve l'intervalle qu'il avait à ce
/// moment-là. Un changement d'intervalle prend donc effet au prochain affichage de l'écran,
/// pas sur un écran déjà ouvert. Les coordonnées de l'école, elles, sont relues à chaque
/// usage et changent immédiatement.
class ParamsService {
  ParamsService(this._get);

  /// Injecté (et non `Api.instance`) pour que les tests puissent fournir leur propre source —
  /// c'est la couture qui manquait à `parent-mobile` et la limitait à 16 tests.
  final Future<List<dynamic>> Function() _get;

  static const _cleCache = 'ts_parametres_cache';

  /// Charge depuis le serveur ; en cas d'échec, retombe sur le cache local.
  /// Ne lève jamais : l'application doit démarrer même si MS13 est absent.
  Future<void> charger() async {
    try {
      final liste = await _get();
      final valeurs = <String, String>{
        for (final p in liste)
          if (p is Map && p['cle'] is String) p['cle'] as String: '${p['valeur']}',
      };
      Env.appliquer(valeurs);
      await _memoriser(valeurs);
    } catch (_) {
      await chargerDepuisCache();
    }
  }

  /// À appeler AVANT le premier rendu : évite que l'école s'affiche une fraction de seconde
  /// au mauvais endroit sur la carte quand le serveur est lent.
  Future<void> chargerDepuisCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final brut = prefs.getString(_cleCache);
      if (brut == null) return;
      final map = (jsonDecode(brut) as Map).cast<String, dynamic>();
      Env.appliquer(map.map((k, v) => MapEntry(k, '$v')));
    } catch (_) {
      // Cache illisible (format changé, écriture interrompue) : on garde les valeurs compilées.
    }
  }

  Future<void> _memoriser(Map<String, String> valeurs) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cleCache, jsonEncode(valeurs));
    } catch (_) {
      // Échec d'écriture du cache : sans conséquence, on relira le serveur au prochain lancement.
    }
  }
}
