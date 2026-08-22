import 'dart:async';

import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/screens/tournee_screen.dart';
import 'package:chauffeur_app/services/outbox.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/fake_api.dart';
import 'helpers/harness.dart';

void main() {
  late FakeApi api;
  late Outbox outbox;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    api = FakeApi();
    outbox = Outbox(api, store: MemoryOutboxStore());
  });

  tearDown(() => outbox.dispose());

  Future<void> monter(WidgetTester tester) async {
    grandEcran(tester);
    await tester.pumpWidget(
      monterEcran(const TourneeScreen(), api: api, outbox: outbox),
    );
    await tester.pumpAndSettle();
  }

  /// Le nom d'un élève peut apparaître deux fois (ligne de liste + KPI
  /// « prochain arrêt ») : on vise la ligne par sa clé, pas par son texte.
  Future<void> pointer(WidgetTester tester, int eleveId) async {
    await tester.tap(find.byKey(ValueKey(eleveId)));
  }

  Future<void> demarrer(WidgetTester tester) async {
    await tester.ensureVisible(find.text('Démarrer le trajet'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Démarrer le trajet'));
    await tester.pumpAndSettle();
  }

  group('Affichage', () {
    testWidgets('Given un chauffeur avec un bus, '
        'Then ses élèves apparaissent dans l\'ordre de passage', (
      tester,
    ) async {
      await monter(tester);

      expect(find.text('MEK-107'), findsWidgets);
      expect(find.text('Amine Idrissi'), findsOneWidget);
      expect(find.text('Salma Bennani'), findsOneWidget);
      expect(find.text('Youssef Alaoui'), findsOneWidget);
      expect(find.text('Démarrer le trajet'), findsOneWidget);
    });

    testWidgets(
      'Given un chauffeur sans bus affecté, Then on le lui dit clairement',
      (tester) async {
        api.buses = [];
        await monter(tester);

        expect(find.textContaining('Aucun bus ne vous est affecté'), findsOne);
      },
    );

    testWidgets('Given un trajet du matin en cours, '
        'Then le prochain arrêt est le premier élève non monté', (
      tester,
    ) async {
      api.eleves = [
        FakeApi.elevesParDefaut()[0].copyWith(statutPresence: true),
        FakeApi.elevesParDefaut()[1],
        FakeApi.elevesParDefaut()[2],
      ];
      await monter(tester);
      await demarrer(tester);

      // Amine est déjà à bord, donc le prochain arrêt est Salma.
      expect(find.text('à bord'), findsOneWidget);
      expect(
        find.text('Salma Bennani'),
        findsNWidgets(2),
        reason:
            'une fois dans la liste, une fois dans le KPI « prochain '
            'arrêt » — c\'est ce doublon qui prouve la sélection',
      );
      expect(find.text('Youssef Alaoui'), findsOneWidget);
      expect(find.textContaining('prochain arrêt'), findsWidgets);
    });
  });

  group('Démarrage du trajet', () {
    testWidgets('Given une tournée chargée, '
        'When le chauffeur démarre, '
        'Then groupeId ET géométrie partent vers MS1', (tester) async {
      await monter(tester);
      await demarrer(tester);

      expect(api.demarrages, hasLength(1));
      final envoi = api.demarrages.single;
      expect(envoi['busId'], 7);
      expect(envoi['sens'], 'MATIN');
      expect(
        envoi['groupeId'],
        3,
        reason:
            'MS11 fige la route par groupe : sans groupeId, pas de '
            'surveillance de déviation.',
      );
      // LE point critique : sans géométrie, MS1 persiste un trajet sans
      // itinéraire et MS11 ne peut plus détecter de déviation — en silence.
      expect(envoi['geometrie'], isNotNull);
      expect((envoi['geometrie'] as List).length, greaterThanOrEqualTo(2));
      // Totaux OSRM figés → chauffeur et parents dérivent la même vitesse
      // de circuit, donc le même ETA.
      expect(envoi['distancePlanM'], 6000);
      expect(envoi['dureePlanMin'], 20);
    });

    testWidgets('Given MS5 injoignable et aucun itinéraire en cache, '
        'Then le démarrage est refusé plutôt que fait à l\'aveugle', (
      tester,
    ) async {
      api.echecTournee = OfflineException();
      await monter(tester);

      final bouton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Démarrer le trajet'),
      );
      expect(
        bouton.onPressed,
        isNull,
        reason:
            'Démarrer sans géométrie désarmerait MS11 sans erreur '
            'visible : on préfère bloquer.',
      );
      expect(
        find.textContaining('En attente de l\'itinéraire'),
        findsOneWidget,
      );
      expect(api.demarrages, isEmpty);
    });

    testWidgets('Given le réseau coupé au moment de démarrer, '
        'Then le trajet passe en file et l\'écran le signale', (tester) async {
      api.echecDemarrer = OfflineException();
      await monter(tester);
      await demarrer(tester);

      expect(outbox.pendingCount, 1);
      expect(outbox.pending.single.kind, OutboxKind.trajetDemarrer);
      // La géométrie doit être conservée DANS la file, sinon le rejeu
      // recréerait un trajet sans itinéraire.
      expect(outbox.pending.single.payload['geometrie'], isNotNull);
      expect(find.textContaining('en attente d\'envoi'), findsWidgets);
    });
  });

  group('Pointage des présences', () {
    testWidgets('Given un trajet en cours, '
        'When le chauffeur pointe une montée, '
        'Then la coche apparaît AVANT la réponse du serveur', (tester) async {
      final serveur = Completer<void>();
      await monter(tester);
      await demarrer(tester);

      api.presenceEnAttente = serveur.future;
      await pointer(tester, 1);
      await tester.pump(); // un seul frame : le serveur n'a pas répondu

      // L'indicateur de pointage en vol est visible → l'UI a déjà basculé.
      expect(find.byType(CircularProgressIndicator), findsWidgets);

      serveur.complete();
      await tester.pumpAndSettle();

      expect(api.presences, [
        {'eleveId': 1, 'present': true},
      ]);
    });

    testWidgets('Given un pointage refusé par le serveur, '
        'Then la coche revient en arrière et l\'erreur est affichée', (
      tester,
    ) async {
      api.echecPresence = ApiException('Élève introuvable');
      await monter(tester);
      await demarrer(tester);

      expect(find.text('à monter'), findsNWidgets(3));

      await pointer(tester, 1);
      await tester.pumpAndSettle();

      // Rollback : les trois élèves sont de nouveau « à monter ».
      expect(
        find.text('à monter'),
        findsNWidgets(3),
        reason:
            'Laisser une coche que la base ne connaît pas ferait croire '
            'au chauffeur qu\'un enfant est à bord.',
      );
      expect(find.text('Élève introuvable'), findsOneWidget);
      expect(outbox.pendingCount, 0, reason: 'refus métier ≠ hors ligne');
    });

    testWidgets('Given le réseau coupé, '
        'When le chauffeur pointe, '
        'Then la coche reste et le pointage part en file', (tester) async {
      api.echecPresence = OfflineException();
      await monter(tester);
      await demarrer(tester);

      await pointer(tester, 1);
      await tester.pumpAndSettle();

      expect(outbox.pendingCount, 1);
      expect(outbox.pending.single.kind, OutboxKind.presence);
      expect(outbox.pending.single.payload['eleveId'], 1);
      expect(outbox.pending.single.payload['present'], true);
      // La valeur optimiste est conservée : deux « à monter » sur trois.
      expect(find.text('à bord'), findsOneWidget);
    });

    testWidgets('Given un trajet non démarré, Then le pointage est inactif', (
      tester,
    ) async {
      await monter(tester);

      await pointer(tester, 1);
      await tester.pumpAndSettle();

      expect(
        api.presences,
        isEmpty,
        reason:
            'Pointer hors trajet produirait des présences non '
            'rattachables à une tournée.',
      );
    });
  });

  group('Fin du trajet', () {
    testWidgets(
      'Given un trajet en cours, When on le termine, Then MS1 est appelé',
      (tester) async {
        await monter(tester);
        await demarrer(tester);
        expect(find.text('Terminer le trajet'), findsOneWidget);

        await tester.ensureVisible(find.text('Terminer le trajet'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Terminer le trajet'));
        await tester.pumpAndSettle();

        expect(api.trajetActif, isNull);
        expect(find.text('Démarrer le trajet'), findsOneWidget);
      },
    );

    testWidgets(
      'Given un démarrage encore en file (jamais reçu par MS1), '
      'When le chauffeur termine, '
      'Then le démarrage en attente est annulé au lieu d\'être envoyé pour rien',
      (tester) async {
        api.echecDemarrer = OfflineException();
        await monter(tester);
        await demarrer(tester);
        expect(outbox.pendingCount, 1);

        await tester.ensureVisible(find.text('Terminer le trajet'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Terminer le trajet'));
        await tester.pumpAndSettle();

        expect(
          outbox.pendingCount,
          0,
          reason:
              'Envoyer un démarrage puis une clôture pour un trajet que '
              'personne n\'a jamais vu polluerait l\'historique.',
        );
        expect(find.text('Démarrer le trajet'), findsOneWidget);
      },
    );
  });
}
