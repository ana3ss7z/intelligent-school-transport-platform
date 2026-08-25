import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'api/api.dart';
import 'services/auth_store.dart';
import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'state/providers.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('fr_FR', null);

  // Restaure la session avant de démarrer l'UI.
  final store = AuthStore();
  final user = await store.load();
  if (user != null) Api.instance.token = user.token;

  final container = ProviderContainer(
    overrides: [initialUserProvider.overrideWithValue(user)],
  );

  // Paramètres applicatifs (MS13). Le cache local est appliqué d'abord, de façon à ce que
  // le premier rendu utilise déjà les bonnes coordonnées d'école — sinon, sur un réseau lent,
  // la carte se centrerait un instant au mauvais endroit. La lecture réseau suit, sans
  // bloquer le démarrage.
  final params = container.read(paramsServiceProvider);
  await params.chargerDepuisCache();
  if (user != null) unawaited(params.charger());

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const ParentApp(),
    ),
  );
}

class ParentApp extends ConsumerWidget {
  const ParentApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider);
    final themeMode = ref.watch(themeModeProvider);
    return MaterialApp(
      title: 'Transport Scolaire — Parent',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: themeMode,
      themeAnimationDuration: const Duration(milliseconds: 300),
      home: user == null ? const LoginScreen() : const ParentShell(),
    );
  }
}
