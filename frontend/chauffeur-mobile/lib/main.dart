import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'services/auth_store.dart';
import 'state/providers.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('fr_FR', null);

  // Restaure la session avant de démarrer l'UI.
  final store = AuthStore();
  final user = await store.load();

  final container = ProviderContainer(
    overrides: [initialUserProvider.overrideWithValue(user)],
  );
  if (user != null) container.read(apiProvider).token = user.token;

  // La file d'attente est relue AVANT le premier rendu : des pointages faits
  // hors ligne lors de la session précédente doivent être visibles tout de
  // suite, pas apparaître quelques secondes après l'ouverture.
  await container.read(outboxProvider).init();
  await container.read(gpsEmitterProvider).init();

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const ChauffeurApp(),
    ),
  );
}

class ChauffeurApp extends ConsumerWidget {
  const ChauffeurApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider);
    final themeMode = ref.watch(themeModeProvider);
    return MaterialApp(
      title: 'Transport Scolaire — Chauffeur',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: themeMode,
      themeAnimationDuration: const Duration(milliseconds: 300),
      home: user == null ? const LoginScreen() : const ChauffeurShell(),
    );
  }
}
