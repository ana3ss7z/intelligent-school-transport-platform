import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/screens/historique_screen.dart';
import 'package:chauffeur_app/screens/map_screen.dart';
import 'package:chauffeur_app/screens/notifications_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/fake_api.dart';
import 'helpers/harness.dart';

/// Les trois écrans de consultation. Ils n'écrivent rien, donc les tests sont
/// courts : ce qu'on veut garantir, c'est qu'ils se rendent, qu'ils disent
/// quelque chose quand il n'y a rien à montrer, et qu'un réseau coupé ne les
/// laisse pas sur un écran blanc.
void main() {
  late FakeApi api;

  setUpAll(() => initializeDateFormatting('fr_FR', null));

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    api = FakeApi();
  });

  Future<void> monter(WidgetTester tester, Widget ecran) async {
    grandEcran(tester);
    await tester.pumpWidget(monterEcran(ecran, api: api, avecScaffold: false));
    await tester.pumpAndSettle();
  }

  group('Ma carte', () {
    testWidgets('Given le bus du chauffeur, '
        'Then la carte se rend avec la tournée et les arrêts', (tester) async {
      grandEcran(tester);
      await tester.pumpWidget(monterEcran(const MapScreen(), api: api));
      await tester.pumpAndSettle();

      expect(find.byType(FlutterMap), findsOneWidget);
      expect(find.byType(PolylineLayer), findsWidgets);
      expect(tester.takeException(), isNull);
    });

    testWidgets(
      'Given un chauffeur sans bus, Then la carte le dit au lieu de rester vide',
      (tester) async {
        api.buses = [];
        grandEcran(tester);
        await tester.pumpWidget(monterEcran(const MapScreen(), api: api));
        await tester.pumpAndSettle();

        expect(find.textContaining('Aucun bus ne vous est affecté'), findsOne);
      },
    );

    testWidgets('Given le WebSocket GPS déconnecté, Then l\'état est affiché', (
      tester,
    ) async {
      grandEcran(tester);
      await tester.pumpWidget(monterEcran(const MapScreen(), api: api));
      await tester.pumpAndSettle();

      // Le socket de test ne se connecte jamais (autoConnect: false) :
      // l'écran doit l'annoncer, pas faire croire à un direct.
      expect(find.text('hors ligne'), findsOneWidget);
    });
  });

  group('Mes notifications', () {
    testWidgets(
      'Given des notifications, Then chacune affiche son titre et son message',
      (tester) async {
        api.notifications = [
          NotificationItem(
            id: 1,
            type: 'INCIDENT_RESOLU',
            titre: 'Incident résolu',
            message: 'La déviation est levée.',
            dateEnvoi: DateTime.now().toIso8601String(),
          ),
          NotificationItem(
            id: 2,
            type: 'MESSAGE_ADMIN',
            titre: 'Message de l\'administration',
            message: 'Merci de passer au dépôt.',
            dateEnvoi: DateTime.now().toIso8601String(),
          ),
        ];
        await monter(tester, const NotificationsScreen());

        expect(find.text('Incident résolu'), findsOneWidget);
        expect(find.text('La déviation est levée.'), findsOneWidget);
        expect(find.text('Merci de passer au dépôt.'), findsOneWidget);
      },
    );

    testWidgets('Given aucune notification, Then l\'écran le dit', (
      tester,
    ) async {
      await monter(tester, const NotificationsScreen());
      expect(find.text('Aucune notification.'), findsOneWidget);
    });

    testWidgets('Given le réseau coupé au premier chargement, '
        'Then une erreur et un réessai sont proposés', (tester) async {
      final apiKo = _ApiInjoignable();
      grandEcran(tester);
      await tester.pumpWidget(
        monterEcran(
          const NotificationsScreen(),
          api: apiKo,
          avecScaffold: false,
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Réessayer'), findsOneWidget);
    });
  });

  group('Mes trajets', () {
    testWidgets(
      'Given des trajets terminés, Then leur sens et leur durée s\'affichent',
      (tester) async {
        api.historique = [
          Trajet(
            id: 10,
            busId: 7,
            sens: 'MATIN',
            statut: 'TERMINE',
            heureDebut: DateTime(2026, 8, 18, 7, 30).toIso8601String(),
            heureFin: DateTime(2026, 8, 18, 8, 12).toIso8601String(),
          ),
          Trajet(
            id: 11,
            busId: 7,
            sens: 'SOIR',
            statut: 'TERMINE',
            heureDebut: DateTime(2026, 8, 18, 17, 30).toIso8601String(),
            heureFin: DateTime(2026, 8, 18, 19, 5).toIso8601String(),
          ),
        ];
        await monter(tester, const HistoriqueScreen());

        expect(find.textContaining('Matin'), findsOneWidget);
        expect(find.textContaining('Soir'), findsOneWidget);
        expect(find.text('42 min'), findsOneWidget);
        expect(find.text('1 h 35'), findsOneWidget);
      },
    );

    testWidgets('Given aucun trajet, Then l\'écran le dit', (tester) async {
      await monter(tester, const HistoriqueScreen());
      expect(find.textContaining('Aucun trajet terminé'), findsOneWidget);
    });
  });
}

/// Backend injoignable, pour les chemins d'erreur.
class _ApiInjoignable extends FakeApi {
  @override
  Future<List<NotificationItem>> getMesNotifications() async =>
      throw OfflineException();
}
