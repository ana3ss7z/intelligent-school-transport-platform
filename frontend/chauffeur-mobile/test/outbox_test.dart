import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/services/outbox.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers/fake_api.dart';

void main() {
  late FakeApi api;
  late MemoryOutboxStore store;
  late Outbox outbox;

  setUp(() {
    api = FakeApi();
    store = MemoryOutboxStore();
    outbox = Outbox(api, store: store);
  });

  tearDown(() => outbox.dispose());

  group('Ordre et vidange', () {
    test('Given un démarrage puis deux pointages, '
        'When le réseau revient, '
        'Then tout part dans l\'ordre où le chauffeur l\'a fait', () async {
      await outbox.enqueue(OutboxKind.trajetDemarrer, {
        'busId': 7,
        'sens': 'MATIN',
        'groupeId': 3,
        'geometrie': FakeApi.tourneeParDefaut.geometrie,
      });
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 1,
        'present': true,
      });
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 2,
        'present': true,
      });

      await outbox.drain();

      expect(outbox.isEmpty, isTrue);
      expect(api.demarrages, hasLength(1));
      expect(
        api.presences.map((p) => p['eleveId']),
        [1, 2],
        reason:
            'Le démarrage doit précéder les pointages, sinon ils portent sur '
            'un trajet qui n\'existe pas encore.',
      );
    });

    test('Given un item qui échoue faute de réseau, '
        'Then la file s\'arrête là et ne double pas les suivants', () async {
      api.echecPresence = OfflineException();
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 1,
        'present': true,
      });
      await outbox.enqueue(OutboxKind.message, {'contenu': 'coucou'});

      await outbox.drain();

      expect(outbox.pendingCount, 2, reason: 'rien ne doit être consommé');
      expect(
        api.messagesEnvoyes,
        isEmpty,
        reason:
            'Laisser passer le message pendant que le pointage bloque '
            'inverserait l\'ordre voulu par le chauffeur.',
      );
    });
  });

  group('Présence — écriture idempotente', () {
    test('Given un chauffeur qui hésite (monté → pas monté → monté), '
        'Then un seul appel part, avec la dernière valeur', () async {
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 1,
        'present': true,
      });
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 1,
        'present': false,
      });
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 1,
        'present': true,
      });

      expect(outbox.pendingCount, 1);
      await outbox.drain();
      expect(api.presences, [
        {'eleveId': 1, 'present': true},
      ]);
    });

    test('Given deux élèves différents, '
        'Then aucun des deux pointages n\'est absorbé par l\'autre', () async {
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 1,
        'present': true,
      });
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 2,
        'present': true,
      });
      expect(outbox.pendingCount, 2);
    });
  });

  group('Réconciliation des opérations non idempotentes', () {
    test(
      'Given un démarrage rejoué alors que MS1 a déjà créé le trajet, '
      'When MS1 répond « un trajet est déjà en cours », '
      'Then on adopte le trajet existant au lieu de boucler sur l\'erreur',
      () async {
        // MS1 refuse un second démarrage (TrajetService.demarrer lève si un
        // trajet EN_COURS existe déjà sur ce bus).
        api.echecDemarrer = ApiException(
          'Un trajet est déjà en cours pour ce bus (id=900).',
        );
        api.trajetActif = Trajet(id: 900, busId: 7, sens: 'MATIN');

        Trajet? adopte;
        outbox.events.listen((e) {
          if (e is TrajetDemarreSync) adopte = e.trajet;
        });

        await outbox.enqueue(OutboxKind.trajetDemarrer, {
          'busId': 7,
          'sens': 'MATIN',
          'groupeId': 3,
        });
        await outbox.drain();
        await Future<void>.delayed(Duration.zero); // laisse passer l'événement

        expect(outbox.isEmpty, isTrue);
        expect(outbox.parkedCount, 0);
        expect(adopte?.id, 900);
      },
    );

    test(
      'Given un démarrage refusé ET aucun trajet actif côté serveur, '
      'Then il n\'y a rien à adopter : l\'item finit par être mis de côté',
      () async {
        api.echecDemarrer = ApiException('Bus inconnu');
        api.trajetActif = null;

        await outbox.enqueue(OutboxKind.trajetDemarrer, {
          'busId': 7,
          'sens': 'MATIN',
        });
        for (var i = 0; i < 4; i++) {
          await outbox.drain();
        }

        expect(outbox.parkedCount, 1);
        expect(outbox.pendingCount, 0);
      },
    );

    test('Given une clôture rejouée alors que le trajet est déjà terminé, '
        'Then l\'item est consommé sans erreur visible', () async {
      api.echecTerminer = ApiException('Trajet introuvable : 900');
      api.trajetActif = null;

      var termine = false;
      outbox.events.listen((e) {
        if (e is TrajetTermineSync) termine = true;
      });

      await outbox.enqueue(OutboxKind.trajetTerminer, {'trajetId': 900});
      await outbox.drain();
      await Future<void>.delayed(Duration.zero);

      expect(outbox.isEmpty, isTrue);
      expect(termine, isTrue);
    });
  });

  group('Plafond d\'essais', () {
    test(
      'Given un incident refusé par le serveur, '
      'Then il est mis de côté après 3 essais au lieu de boucler à l\'infini',
      () async {
        api.echecIncident = ApiException('Type invalide');
        await outbox.enqueue(OutboxKind.incident, {
          'type': 'PANNE',
          'busId': 7,
        });

        await outbox.drain();
        expect(outbox.pendingCount, 1, reason: 'essai 1');
        await outbox.drain();
        expect(outbox.pendingCount, 1, reason: 'essai 2');
        await outbox.drain();

        expect(outbox.pendingCount, 0);
        expect(outbox.parkedCount, 1);
        expect(outbox.parked.single.lastError, contains('Type invalide'));
      },
    );

    test('Given un item mis de côté puis relancé par le chauffeur, '
        'When le serveur accepte cette fois, '
        'Then il part normalement', () async {
      api.echecIncident = ApiException('Serveur occupé');
      await outbox.enqueue(OutboxKind.incident, {'type': 'PANNE', 'busId': 7});
      for (var i = 0; i < 3; i++) {
        await outbox.drain();
      }
      expect(outbox.parkedCount, 1);

      api.echecIncident = null;
      await outbox.retryParked(outbox.parked.single.id);
      await outbox.drain();

      expect(outbox.isEmpty, isTrue);
      expect(api.incidentsCrees, hasLength(1));
    });
  });

  group('Persistance', () {
    test('Given des actions faites hors ligne puis l\'app tuée, '
        'When elle redémarre, '
        'Then rien n\'est perdu', () async {
      await outbox.enqueue(OutboxKind.presence, {
        'eleveId': 5,
        'present': true,
        'nom': 'Amine Idrissi',
      });
      await outbox.enqueue(OutboxKind.incident, {
        'type': 'PANNE',
        'busId': 7,
        'description': 'pneu crevé',
      });

      // Nouvelle instance sur le même stockage = relance de l'app.
      final apres = Outbox(api, store: store);
      await apres.init();

      expect(apres.pendingCount, 2);
      expect(apres.pending.first.payload['eleveId'], 5);
      expect(apres.pending.last.payload['description'], 'pneu crevé');

      await apres.drain();
      expect(api.presences, hasLength(1));
      expect(api.incidentsCrees, hasLength(1));
      apres.dispose();
    });

    test(
      'Given une file vidée, '
      'Then le stockage l\'est aussi (pas de rejeu fantôme au prochain lancement)',
      () async {
        await outbox.enqueue(OutboxKind.message, {'contenu': 'test'});
        await outbox.drain();

        final apres = Outbox(api, store: store);
        await apres.init();
        expect(apres.isEmpty, isTrue);
        apres.dispose();
      },
    );
  });
}
