import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:parent_app/screens/login_screen.dart';
import 'package:parent_app/theme.dart';

void main() {
  testWidgets('L\'écran de login s\'affiche', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(theme: buildTheme(), home: const LoginScreen()),
      ),
    );
    expect(find.text('Espace parent'), findsOneWidget);
    expect(find.text('Se connecter'), findsOneWidget);
  });
}
