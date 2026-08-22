import 'dart:async';

import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/screens/eta_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/fake_api.dart';
import 'helpers/harness.dart';

void main() {
  late FakeApi api;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    api = FakeApi();
  });

  Future<void> monter(WidgetTester tester) async {
    grandEcran(tester);
    await tester.pumpWidget(
      monterEcran(const EtaScreen(), api: api, avecScaffold: false),
    );
    await tester.pumpAndSettle();
  }

  Future<void> calculer(WidgetTester tester) async {
    await tester.ensureVisible(find.text('Calculer'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Calculer'));
  }

  testWidgets('Given un calcul en cours, '
      'Then l\'état de chargement se rend sans casser la mise en page', (
    tester,
  ) async {
    // Régression : le squelette était un ListView imbriqué dans le ListView de
    // l'écran → hauteur infinie → les RenderBox n'étaient jamais dimensionnés.
    // Symptôme observé : le résultat s'affichait, mais plus rien n'était
    // cliquable (le hit-test ne trouvait plus de boîte) et `mouse_tracker`
    // partait en assertion. Invisible chez le parent (1–3 enfants, squelette
    // affiché une fraction de seconde), bloquant chez le chauffeur (50 arrêts).
    final serveur = Completer<void>();
    api.tourneeEnAttente = serveur.future;

    await monter(tester);
    await calculer(tester);
    await tester.pump(); // frame affichant l'état de chargement

    expect(find.text('Calcul…'), findsOneWidget);
    expect(
      tester.takeException(),
      isNull,
      reason: 'aucune exception de layout pendant le chargement',
    );

    serveur.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('Given une tournée planifiée, '
      'Then chaque arrêt affiche son rang, son heure et sa distance', (
    tester,
  ) async {
    await monter(tester);
    await calculer(tester);
    await tester.pumpAndSettle();

    expect(find.text('Amine Idrissi'), findsOneWidget);
    expect(find.text('Salma Bennani'), findsOneWidget);
    expect(find.text('Youssef Alaoui'), findsOneWidget);
    // MS12 renvoie 12 min pour chaque étape (FakeApi) et le départ est 07:30.
    expect(find.text('07:42'), findsNWidgets(3));
    expect(find.textContaining('km depuis l\'école'), findsNWidgets(3));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Given un résultat affiché, Then l\'écran reste interactif', (
    tester,
  ) async {
    await monter(tester);
    await calculer(tester);
    await tester.pumpAndSettle();

    // Le vrai symptôme rapporté : « ça affiche le résultat mais je n'arrive
    // plus à cliquer ». On re-déclenche donc une interaction APRÈS le rendu.
    await tester.tap(find.text('Soir'));
    await tester.pumpAndSettle();

    expect(
      find.text('Amine Idrissi'),
      findsNothing,
      reason:
          'changer de sens doit vider les résultats — donc le bouton a '
          'bien reçu le tap',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Given MS5 injoignable, Then l\'erreur est affichée avec un réessai',
    (tester) async {
      api.echecTournee = ApiException('Planification indisponible');
      await monter(tester);
      await calculer(tester);
      await tester.pumpAndSettle();

      expect(find.text('Planification indisponible'), findsOneWidget);
      expect(find.text('Réessayer'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Given MS12 muet sur une étape, '
      'Then on retombe sur la durée OSRM au lieu de laisser un trou', (
    tester,
  ) async {
    final apiSansEta = _ApiSansEta();
    grandEcran(tester);
    await tester.pumpWidget(
      monterEcran(const EtaScreen(), api: apiSansEta, avecScaffold: false),
    );
    await tester.pumpAndSettle();
    await calculer(tester);
    await tester.pumpAndSettle();

    // cumul_duree_s = 300 / 600 / 900 → 5, 10 et 15 min après 07:30.
    expect(find.text('07:35'), findsOneWidget);
    expect(find.text('07:40'), findsOneWidget);
    expect(find.text('07:45'), findsOneWidget);
    expect(find.textContaining('estimation OSRM'), findsNWidgets(3));
  });
}

/// MS12 en panne : l'écran doit rester exploitable.
class _ApiSansEta extends FakeApi {
  @override
  Future<EtaResult> predictEta({
    double? busLat,
    double? busLng,
    double? destLat,
    double? destLng,
    double? distanceRoutiereM,
    double? dureeBaseS,
    double? heureDepart,
    required String moment,
  }) async => throw ApiException('ETA indisponible');
}
