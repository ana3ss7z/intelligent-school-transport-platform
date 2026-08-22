import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/screens/incidents_screen.dart';
import 'package:chauffeur_app/services/outbox.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'helpers/fake_api.dart';
import 'helpers/harness.dart';

void main() {
  late FakeApi api;
  late Outbox outbox;

  setUpAll(() => initializeDateFormatting('fr_FR', null));

  setUp(() {
    api = FakeApi();
    outbox = Outbox(api, store: MemoryOutboxStore());
  });

  tearDown(() => outbox.dispose());

  Future<void> monter(WidgetTester tester) async {
    grandEcran(tester);
    await tester.pumpWidget(
      monterEcran(
        const IncidentsScreen(),
        api: api,
        outbox: outbox,
        avecScaffold: false,
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> ouvrirFormulaire(WidgetTester tester) async {
    await tester.tap(find.text('Signaler'));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Given aucun incident, Then l\'écran le dit et propose d\'en signaler un',
    (tester) async {
      await monter(tester);

      expect(find.textContaining('Aucun incident signalé'), findsOneWidget);
      expect(find.text('Signaler'), findsOneWidget);
    },
  );

  testWidgets(
    'Given des incidents existants, Then leur type et leur statut s\'affichent',
    (tester) async {
      api.incidents = [
        Incident(
          id: 1,
          type: 'ROUTE_BLOQUEE',
          statut: 'RESOLU',
          busId: 7,
          description: 'Manifestation avenue Hassan II',
          notesResolution: 'Déviation mise en place',
          dateSignalement: DateTime.now().toIso8601String(),
        ),
        Incident(
          id: 2,
          type: 'PANNE',
          statut: 'SIGNALE',
          busId: 7,
          dateSignalement: DateTime.now().toIso8601String(),
        ),
      ];
      await monter(tester);

      expect(find.text('ROUTE BLOQUEE'), findsOneWidget);
      expect(find.text('PANNE'), findsOneWidget);
      expect(find.text('résolu'), findsOneWidget);
      expect(find.text('signalé'), findsOneWidget);
      expect(find.textContaining('Déviation mise en place'), findsOneWidget);
    },
  );

  testWidgets('Given le formulaire ouvert, '
      'When le chauffeur signale une panne, '
      'Then le type, la description et le bus partent vers MS10', (
    tester,
  ) async {
    await monter(tester);
    await ouvrirFormulaire(tester);

    await tester.enterText(find.byType(TextField), 'Pneu arrière crevé');
    await tester.tap(find.widgetWithText(FilledButton, 'Signaler'));
    await tester.pumpAndSettle();

    expect(api.incidentsCrees, hasLength(1));
    final envoi = api.incidentsCrees.single;
    expect(envoi['type'], 'PANNE'); // premier type de la liste
    expect(envoi['busId'], 7);
    expect(envoi['description'], 'Pneu arrière crevé');
  });

  testWidgets(
    'Given un autre type choisi dans la liste, Then c\'est celui-là qui part',
    (tester) async {
      await monter(tester);
      await ouvrirFormulaire(tester);

      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('ACCIDENT').last);
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Signaler'));
      await tester.pumpAndSettle();

      expect(api.incidentsCrees.single['type'], 'ACCIDENT');
    },
  );

  testWidgets('Given le réseau coupé, '
      'When le chauffeur signale un incident, '
      'Then il part en file au lieu d\'être perdu', (tester) async {
    // C'est le cas qui compte : on signale un incident précisément là où ça
    // va mal, souvent là où le réseau est mauvais.
    api.echecIncident = OfflineException();
    await monter(tester);
    await ouvrirFormulaire(tester);

    await tester.enterText(find.byType(TextField), 'Moteur qui fume');
    await tester.tap(find.widgetWithText(FilledButton, 'Signaler'));
    await tester.pumpAndSettle();

    expect(outbox.pendingCount, 1);
    expect(outbox.pending.single.kind, OutboxKind.incident);
    expect(outbox.pending.single.payload['description'], 'Moteur qui fume');
    expect(outbox.pending.single.payload['busId'], 7);
  });

  testWidgets('Given un signalement refusé par le serveur, '
      'Then le formulaire reste ouvert avec les données saisies', (
    tester,
  ) async {
    api.echecIncident = ApiException('Type inconnu');
    await monter(tester);
    await ouvrirFormulaire(tester);

    await tester.enterText(find.byType(TextField), 'Texte à conserver');
    await tester.tap(find.widgetWithText(FilledButton, 'Signaler'));
    await tester.pumpAndSettle();

    expect(
      find.widgetWithText(FilledButton, 'Signaler'),
      findsOneWidget,
      reason: 'fermer le dialogue ferait perdre la saisie du chauffeur',
    );
    expect(find.text('Texte à conserver'), findsOneWidget);
    expect(outbox.pendingCount, 0);
  });
}
