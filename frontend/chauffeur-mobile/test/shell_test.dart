import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/screens/shell.dart';
import 'package:chauffeur_app/services/outbox.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/fake_api.dart';
import 'helpers/harness.dart';

/// La coque de l'app : c'est le seul écran « de structure » qui porte de la
/// logique, et l'un de ses effets est invisible — si `OutboxSync` n'est pas
/// démarré, la file d'écritures différées ne se vide jamais et **rien ne le
/// signale** : le chauffeur voit ses pointages marqués « en attente » pour
/// toujours. D'où le premier test.
void main() {
  late FakeApi api;
  late Outbox outbox;
  late FakeOutboxSync sync;

  setUpAll(() => initializeDateFormatting('fr_FR', null));

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    api = FakeApi();
    outbox = Outbox(api, store: MemoryOutboxStore());
    sync = FakeOutboxSync(outbox);
  });

  tearDown(() => outbox.dispose());

  Future<void> monter(WidgetTester tester) async {
    grandEcran(tester);
    await tester.pumpWidget(
      monterEcran(
        const ChauffeurShell(),
        api: api,
        outbox: outbox,
        sync: sync,
        avecScaffold: false,
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Given le shell monté, '
      'Then la vidange de la file d\'attente est démarrée', (tester) async {
    expect(sync.demarre, isFalse);
    await monter(tester);
    expect(
      sync.demarre,
      isTrue,
      reason:
          'sans ça, une action faite hors ligne reste en file '
          'indéfiniment, sans aucun signe visible',
    );
  });

  testWidgets(
    'Given les 5 destinations, Then « Ma tournée » est ouverte par défaut',
    (tester) async {
      await monter(tester);

      expect(find.text('Tournée'), findsOneWidget);
      expect(find.text('Carte'), findsOneWidget);
      expect(find.text('Messages'), findsOneWidget);
      expect(find.text('Incidents'), findsOneWidget);
      expect(find.text('Plus'), findsOneWidget);
      // Le titre de l'AppBar reflète l'onglet actif.
      expect(find.widgetWithText(AppBar, 'Ma tournée'), findsOneWidget);
    },
  );

  testWidgets(
    'Given l\'onglet Tournée, When on choisit Carte, Then le titre suit',
    (tester) async {
      await monter(tester);
      await tester.tap(find.text('Carte'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(AppBar, 'Ma carte'), findsOneWidget);
    },
  );

  testWidgets('Given la destination « Plus », '
      'When on la touche, '
      'Then une feuille s\'ouvre SANS quitter l\'onglet courant', (
    tester,
  ) async {
    await monter(tester);
    await tester.tap(find.text('Plus'));
    await tester.pumpAndSettle();

    // Les trois écrans de second rang sont proposés…
    expect(find.text('Prévisions ETA'), findsOneWidget);
    expect(find.text('Mes notifications'), findsOneWidget);
    expect(find.text('Mes trajets'), findsOneWidget);
    expect(find.text('Se déconnecter'), findsOneWidget);
    // …et l'onglet actif n'a pas changé : « Plus » est un menu, pas une page.
    expect(find.widgetWithText(AppBar, 'Ma tournée'), findsOneWidget);
  });

  testWidgets(
    'Given des messages non lus, Then un badge les annonce sur l\'onglet',
    (tester) async {
      api.unread = 3;
      await monter(tester);

      expect(find.widgetWithText(Badge, '3'), findsWidgets);
    },
  );

  testWidgets('Given un badge affiché, '
      'When le réseau tombe au sondage suivant, '
      'Then le compteur garde sa valeur au lieu de disparaître', (
    tester,
  ) async {
    api.unread = 2;
    await monter(tester);
    expect(find.widgetWithText(Badge, '2'), findsWidgets);

    // Un badge qui s'efface ment davantage qu'un badge périmé : le chauffeur
    // en conclurait qu'il a tout lu.
    api.echecUnread = OfflineException();
    await tester.tap(find.text('Messages'));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(Badge, '2'), findsWidgets);
  });

  testWidgets(
    'Given la déconnexion demandée, Then une confirmation est exigée',
    (tester) async {
      await monter(tester);
      await tester.tap(find.text('Plus'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Se déconnecter'));
      await tester.pumpAndSettle();

      expect(find.text('Se déconnecter ?'), findsOneWidget);
      expect(find.text('Annuler'), findsOneWidget);
    },
  );
}
