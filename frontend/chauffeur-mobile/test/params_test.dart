import 'package:flutter_test/flutter_test.dart';
import 'package:chauffeur_app/config/env.dart';
import 'package:chauffeur_app/services/params_service.dart';

/// Paramètres servis par MS13 — application, repli et garde-fous.
///
/// Ce qui est vérifié ici a une conséquence directe en exploitation : une valeur mal
/// convertie ne lève aucune erreur, elle produit une carte centrée au mauvais endroit ou
/// un sondage assez agressif pour se faire refuser par la passerelle.
void main() {
  setUp(Env.reinitialiser);
  tearDownAll(Env.reinitialiser);

  group('Env.appliquer', () {
    test('Given des valeurs serveur, Then elles remplacent les constantes compilées', () {
      Env.appliquer({
        'ecole.lat': '34.05',
        'ecole.lng': '-6.79',
        'ui.poll_trajet_s': '25',
        'ui.poll_eta_s': '45',
      });

      expect(Env.ecoleLat, 34.05);
      expect(Env.ecoleLng, -6.79);
      expect(Env.pollTrajet, const Duration(seconds: 25));
      expect(Env.pollEta, const Duration(seconds: 45));
    });

    test('Given une réponse partielle, Then les clés absentes gardent leur valeur', () {
      Env.appliquer({'ecole.lat': '34.05'});

      expect(Env.ecoleLat, 34.05);
      // Une réponse incomplète ne doit pas dégrader ce qui fonctionnait.
      expect(Env.ecoleLng, -5.5455);
      expect(Env.pollTrajet, const Duration(seconds: 15));
    });

    test('Given une valeur illisible, Then le défaut est conservé', () {
      Env.appliquer({'ecole.lat': 'nawak', 'ui.poll_eta_s': ''});

      expect(Env.ecoleLat, 33.893);
      expect(Env.pollEta, const Duration(seconds: 30));
    });

    test('Given un intervalle sous le plancher, Then il est ramené à 5 s', () {
      // La passerelle plafonne à 20 requêtes/s par adresse et plusieurs sondages tournent
      // en parallèle : un intervalle de 1 s se ferait refuser sans message clair.
      Env.appliquer({'ui.poll_inbox_s': '1'});

      expect(Env.pollInbox, const Duration(seconds: 5));
    });

    test('Given un intervalle nul ou négatif, Then le défaut est conservé', () {
      // Un Timer.periodic(Duration.zero) boucle sans fin sur le processeur.
      Env.appliquer({'ui.poll_unread_s': '0', 'ui.poll_trajet_s': '-30'});

      expect(Env.pollUnread, const Duration(seconds: 20));
      expect(Env.pollTrajet, const Duration(seconds: 15));
    });

    test('Given poll_liste_s, Then présence et conversation le suivent', () {
      // Ces deux sondages n'ont pas de réglage propre côté serveur, mais doivent se
      // desserrer avec les listes quand l'exploitant réduit la charge réseau.
      Env.appliquer({'ui.poll_liste_s': '40'});

      expect(Env.pollPresence, const Duration(seconds: 40));
      expect(Env.pollConversation, const Duration(seconds: 40));
    });
  });

  group('ParamsService', () {
    test('Given MS13 injoignable, Then les valeurs compilées restent en place', () async {
      final service = ParamsService(() async => throw Exception('réseau coupé'));

      await service.charger();   // ne doit pas lever

      expect(Env.ecoleLat, 33.893);
      expect(Env.pollTrajet, const Duration(seconds: 15));
    });

    test('Given une réponse serveur, Then elle est appliquée', () async {
      final service = ParamsService(() async => [
            {'cle': 'ecole.lat', 'valeur': '31.63'},
            {'cle': 'ui.poll_eta_s', 'valeur': '60'},
          ]);

      await service.charger();

      expect(Env.ecoleLat, 31.63);
      expect(Env.pollEta, const Duration(seconds: 60));
    });

    test('Given une entrée malformée, Then elle est ignorée sans faire échouer le reste', () async {
      final service = ParamsService(() async => [
            'pas une map',
            {'pas_de_cle': 1},
            {'cle': 'ecole.lng', 'valeur': '-7.62'},
          ]);

      await service.charger();

      expect(Env.ecoleLng, -7.62);
    });
  });
}
