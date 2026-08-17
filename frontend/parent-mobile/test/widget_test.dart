import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:parent_app/screens/login_screen.dart';
import 'package:parent_app/theme.dart';

Widget _app({Brightness brightness = Brightness.light}) => ProviderScope(
  child: MaterialApp(
    theme: buildTheme(brightness),
    home: const LoginScreen(),
  ),
);

void main() {
  group('LoginScreen', () {
    testWidgets(
      'Given l\'app démarre, When l\'écran de login s\'affiche, '
      'Then le titre et le bouton sont visibles',
      (tester) async {
        await tester.pumpWidget(_app());
        await tester.pumpAndSettle();

        expect(find.text('Bienvenue'), findsOneWidget);
        expect(find.textContaining('Espace parent'), findsOneWidget);
        expect(find.text('Se connecter'), findsOneWidget);
        expect(find.byType(TextFormField), findsNWidgets(2));
      },
    );

    testWidgets(
      'Given des champs vides, When on soumet, Then les erreurs de '
      'validation apparaissent et aucune requête n\'est faite',
      (tester) async {
        await tester.pumpWidget(_app());
        await tester.pumpAndSettle();

        await tester.tap(find.text('Se connecter'));
        await tester.pumpAndSettle();

        expect(find.text('Email invalide'), findsOneWidget);
        expect(find.text('Mot de passe requis'), findsOneWidget);
      },
    );

    testWidgets(
      'Given un email sans @, When on soumet, Then la validation le refuse',
      (tester) async {
        await tester.pumpWidget(_app());
        await tester.pumpAndSettle();

        await tester.enterText(find.byType(TextFormField).first, 'pas-un-email');
        await tester.tap(find.text('Se connecter'));
        await tester.pumpAndSettle();

        expect(find.text('Email invalide'), findsOneWidget);
      },
    );

    testWidgets(
      'Given le mot de passe masqué, When on tape sur l\'œil, '
      'Then il devient visible',
      (tester) async {
        await tester.pumpWidget(_app());
        await tester.pumpAndSettle();

        // Masqué au départ.
        expect(find.byIcon(Icons.visibility_off_outlined), findsOneWidget);

        await tester.tap(find.byIcon(Icons.visibility_off_outlined));
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.visibility_outlined), findsOneWidget);
      },
    );

    testWidgets('Given le thème sombre, Then l\'écran se rend sans erreur', (
      tester,
    ) async {
      await tester.pumpWidget(_app(brightness: Brightness.dark));
      await tester.pumpAndSettle();

      expect(find.text('Bienvenue'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
