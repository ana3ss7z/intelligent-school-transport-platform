import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/screens/messages_screen.dart';
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
      monterEcran(const MessagesScreen(), api: api, outbox: outbox),
    );
    await tester.pumpAndSettle();
  }

  Future<void> ecrireEtEnvoyer(WidgetTester tester, String texte) async {
    await tester.enterText(find.byType(TextField).first, texte);
    await tester.tap(find.byIcon(Icons.send_rounded));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Given une conversation existante, Then les deux côtés sont affichés',
    (tester) async {
      api.conversation = [
        MessageItem(
          id: 1,
          expediteurRole: 'ADMIN',
          expediteurNom: 'Direction',
          contenu: 'Bonjour, tout va bien ce matin ?',
          dateEnvoi: DateTime.now().toIso8601String(),
        ),
        MessageItem(
          id: 2,
          expediteurRole: 'CHAUFFEUR',
          contenu: 'Oui, RAS.',
          dateEnvoi: DateTime.now().toIso8601String(),
        ),
      ];
      await monter(tester);

      expect(find.text('Bonjour, tout va bien ce matin ?'), findsOneWidget);
      expect(find.text('Oui, RAS.'), findsOneWidget);
      expect(find.text('Direction'), findsOneWidget);
    },
  );

  testWidgets(
    'Given un fil vide, Then l\'écran invite à démarrer la conversation',
    (tester) async {
      await monter(tester);
      expect(find.textContaining('Démarrez la conversation'), findsOneWidget);
    },
  );

  testWidgets('Given un message saisi, '
      'When le chauffeur l\'envoie, '
      'Then il part vers MS4 et apparaît dans le fil', (tester) async {
    await monter(tester);
    await ecrireEtEnvoyer(tester, 'Je suis bloqué avenue des FAR.');

    expect(api.messagesEnvoyes, ['Je suis bloqué avenue des FAR.']);
    expect(find.text('Je suis bloqué avenue des FAR.'), findsOneWidget);
  });

  testWidgets('Given le réseau coupé, '
      'When le chauffeur envoie, '
      'Then la bulle reste marquée « en attente » et le message part en file', (
    tester,
  ) async {
    api.echecMessage = OfflineException();
    await monter(tester);
    await ecrireEtEnvoyer(tester, 'Panne moteur.');

    expect(outbox.pendingCount, 1);
    expect(outbox.pending.single.kind, OutboxKind.message);
    expect(outbox.pending.single.payload['contenu'], 'Panne moteur.');
    // Le message ne disparaît pas de l'écran : il est en file, pas perdu.
    expect(find.text('Panne moteur.'), findsOneWidget);
    expect(find.text('en attente'), findsOneWidget);
  });

  testWidgets('Given un envoi refusé par le serveur, '
      'Then la bulle est marquée « non envoyé » avec une action de réessai', (
    tester,
  ) async {
    api.echecMessage = ApiException('Destinataire introuvable');
    await monter(tester);
    await ecrireEtEnvoyer(tester, 'Test');

    expect(find.text('non envoyé'), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
    expect(
      outbox.pendingCount,
      0,
      reason: 'un refus métier ne doit pas être rejoué en boucle',
    );
  });

  testWidgets('Given un message en échec, When on réessaie et que ça passe, '
      'Then il est envoyé pour de bon', (tester) async {
    api.echecMessage = ApiException('Serveur occupé');
    await monter(tester);
    await ecrireEtEnvoyer(tester, 'Retard de 10 min');
    expect(find.text('non envoyé'), findsOneWidget);

    api.echecMessage = null;
    await tester.tap(find.text('Réessayer'));
    await tester.pumpAndSettle();

    expect(api.messagesEnvoyes, ['Retard de 10 min']);
    expect(find.text('non envoyé'), findsNothing);
  });

  group('Diffusion aux parents', () {
    Future<void> ouvrirDiffusion(WidgetTester tester) async {
      await tester.tap(find.text('Diffuser un message aux parents'));
      await tester.pumpAndSettle();
    }

    testWidgets('Given une diffusion, '
        'Then elle part sur le canal parents avec le busId, '
        'et NON dans le fil avec l\'administration', (tester) async {
      await monter(tester);
      await ouvrirDiffusion(tester);

      await tester.enterText(
        find.byType(TextField).last,
        'Léger retard ce matin, ~10 min.',
      );
      await tester.tap(find.text('Diffuser aux parents'));
      await tester.pumpAndSettle();

      expect(api.diffusions, hasLength(1));
      expect(api.diffusions.single['busId'], 7);
      expect(
        api.diffusions.single['contenu'],
        'Léger retard ce matin, ~10 min.',
      );
      expect(
        api.messagesEnvoyes,
        isEmpty,
        reason: 'les deux canaux sont volontairement étanches',
      );
    });

    testWidgets(
      'Given le réseau coupé pendant une diffusion, Then elle part en file',
      (tester) async {
        api.echecDiffusion = OfflineException();
        await monter(tester);
        await ouvrirDiffusion(tester);

        await tester.enterText(find.byType(TextField).last, 'Grève demain');
        await tester.tap(find.text('Diffuser aux parents'));
        await tester.pumpAndSettle();

        expect(outbox.pendingCount, 1);
        expect(outbox.pending.single.kind, OutboxKind.diffusion);
        expect(outbox.pending.single.payload['busId'], 7);
      },
    );
  });
}
