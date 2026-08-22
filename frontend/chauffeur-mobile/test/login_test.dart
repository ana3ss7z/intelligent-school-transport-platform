import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/screens/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers/fake_api.dart';
import 'helpers/harness.dart';

void main() {
  late FakeApi api;

  setUp(() => api = FakeApi());

  /// Le formulaire dépasse le viewport de test (800x600) : on fait défiler
  /// jusqu'au bouton avant de l'actionner.
  Future<void> valider(WidgetTester tester) async {
    await tester.ensureVisible(find.byType(FilledButton));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();
  }

  Future<void> saisirEtValider(
    WidgetTester tester, {
    String email = 'hassan@transport.ma',
    String motDePasse = 'Chauffeur123!',
  }) async {
    await tester.enterText(find.byType(TextFormField).first, email);
    await tester.enterText(find.byType(TextFormField).last, motDePasse);
    await valider(tester);
  }

  testWidgets('Given l\'écran de connexion, Then il s\'affiche sans erreur', (
    tester,
  ) async {
    await tester.pumpWidget(
      monterEcran(
        const LoginScreen(),
        api: api,
        utilisateur: null,
        avecScaffold: false,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Bonjour'), findsOneWidget);
    expect(find.text('Espace chauffeur · Transport scolaire'), findsOneWidget);
    expect(find.byType(TextFormField), findsNWidgets(2));
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Given un formulaire vide, When on valide, Then rien n\'est envoyé',
    (tester) async {
      await tester.pumpWidget(
        monterEcran(
          const LoginScreen(),
          api: api,
          utilisateur: null,
          avecScaffold: false,
        ),
      );
      await valider(tester);

      expect(find.text('Email invalide'), findsOneWidget);
      expect(find.text('Mot de passe requis'), findsOneWidget);
    },
  );

  testWidgets('Given un email sans arobase, Then la validation le refuse', (
    tester,
  ) async {
    await tester.pumpWidget(
      monterEcran(
        const LoginScreen(),
        api: api,
        utilisateur: null,
        avecScaffold: false,
      ),
    );
    await tester.enterText(find.byType(TextFormField).first, 'hassan');
    await tester.enterText(find.byType(TextFormField).last, 'x');
    await valider(tester);

    expect(find.text('Email invalide'), findsOneWidget);
  });

  testWidgets(
    'Given un mot de passe masqué, When on appuie sur l\'œil, Then il s\'affiche',
    (tester) async {
      await tester.pumpWidget(
        monterEcran(
          const LoginScreen(),
          api: api,
          utilisateur: null,
          avecScaffold: false,
        ),
      );
      expect(find.byIcon(Icons.visibility_off_outlined), findsOneWidget);

      await tester.tap(find.byIcon(Icons.visibility_off_outlined));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.visibility_outlined), findsOneWidget);
    },
  );

  testWidgets('Given un compte PARENT valide, '
      'When il se connecte à l\'app chauffeur, '
      'Then la session est refermée et le refus est expliqué', (tester) async {
    // Le mot de passe est bon : MS7 délivre un vrai jeton. C'est le rôle qui
    // ne convient pas — et aucune route de cette app ne lui est ouverte.
    api.echecLogin = null;
    final apiParent = _ApiRolePersonnalise('PARENT');

    await tester.pumpWidget(
      monterEcran(
        const LoginScreen(),
        api: apiParent,
        utilisateur: null,
        avecScaffold: false,
      ),
    );
    await saisirEtValider(tester);

    expect(
      find.text('Ce compte n\'est pas un compte chauffeur.'),
      findsOneWidget,
    );
    // Toujours sur l'écran de connexion : aucune session ouverte.
    expect(find.text('Se connecter'), findsOneWidget);
  });

  testWidgets(
    'Given des identifiants refusés par MS7, Then le message serveur est affiché',
    (tester) async {
      api.echecLogin = ApiException('Email ou mot de passe incorrect.');
      await tester.pumpWidget(
        monterEcran(
          const LoginScreen(),
          api: api,
          utilisateur: null,
          avecScaffold: false,
        ),
      );
      await saisirEtValider(tester);

      expect(find.text('Email ou mot de passe incorrect.'), findsOneWidget);
    },
  );

  testWidgets(
    'Given le thème sombre, Then l\'écran de connexion reste lisible',
    (tester) async {
      await tester.pumpWidget(
        monterEcran(
          const LoginScreen(),
          api: api,
          utilisateur: null,
          avecScaffold: false,
          brightness: Brightness.dark,
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Bonjour'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}

/// Variante renvoyant un rôle choisi, pour tester la garde de rôle.
class _ApiRolePersonnalise extends FakeApi {
  _ApiRolePersonnalise(this.role);
  final String role;

  @override
  Future<AuthUser> login(String email, String motDePasse) async => AuthUser(
    token: 'jwt',
    userId: 1,
    nom: 'Parent Test',
    email: email,
    role: role,
  );
}
