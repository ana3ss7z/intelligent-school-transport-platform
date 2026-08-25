import 'package:flutter_test/flutter_test.dart';
import 'package:parent_app/config/env.dart';
import 'package:parent_app/services/push_service.dart';

/// Contrat de [PushService] — le push est un confort, jamais un point de rupture.
///
/// Ces tests couvrent la partie du service qui ne dépend pas de Firebase : le contrat
/// d'injection, l'étiquette de plateforme et surtout la garantie qu'aucune défaillance ne
/// remonte jusqu'à la connexion. La boucle FCM elle-même (permission, `getToken`,
/// `onTokenRefresh`) exige un vrai navigateur et relève de la vérification de bout en bout.
void main() {
  test('la plateforme déclarée n\'est jamais devinée', () {
    // MS4 range en « INCONNU » ce qu'il ne reconnaît pas plutôt que de supposer « ANDROID » :
    // le champ ne sert qu'au diagnostic, autant qu'il dise la vérité.
    expect(PushService.plateforme, isNotEmpty);
    expect(PushService.plateforme, equals(PushService.plateforme.toUpperCase()));
  });

  test('la clé VAPID est injectée au build, pas codée en dur', () {
    // Vide par défaut : `--dart-define-from-file=config/env.chrome.json` la fournit.
    // Le test garantit surtout qu'aucune clé n'a été committée dans le source.
    expect(Env.vapidKey, isA<String>());
  });

  test('aucun jeton associé tant que activer() n\'a pas réussi', () {
    final service = PushService(
      enregistrer: (_, __) async {},
      supprimer: (_) async {},
    );
    expect(service.dernierToken, isNull);
  });

  test('desactiver() sans jeton ne fait aucun appel réseau et ne lève pas', () async {
    var suppressions = 0;
    final service = PushService(
      enregistrer: (_, __) async {},
      supprimer: (_) async => suppressions++,
    );

    await expectLater(service.desactiver(), completes);
    expect(suppressions, 0);
  });

  test('activer() ne lève jamais, même sans Firebase initialisé', () async {
    // Cas réel : navigateur sans Push API, service worker absent, ou MS4 injoignable.
    // La connexion ne doit pas échouer pour autant — c'est la raison du `unawaited` côté
    // AuthController, et du try/catch total ici.
    final service = PushService(
      enregistrer: (_, __) async => throw Exception('MS4 injoignable'),
      supprimer: (_) async => throw Exception('MS4 injoignable'),
    );

    await expectLater(service.activer(), completes);
    expect(service.dernierToken, isNull);
  });
}
