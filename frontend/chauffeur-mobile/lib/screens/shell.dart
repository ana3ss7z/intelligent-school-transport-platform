import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/env.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/outbox_banner.dart';
import 'eta_screen.dart';
import 'historique_screen.dart';
import 'incidents_screen.dart';
import 'map_screen.dart';
import 'messages_screen.dart';
import 'notifications_screen.dart';
import 'tournee_screen.dart';

/// Coque de l'app : 5 destinations principales + une feuille « Plus ».
///
/// Material 3 plafonne une NavigationBar à 5 destinations ; l'espace chauffeur
/// en compte 7. Les trois écrans consultatifs (prévisions, notifications,
/// historique) passent donc en second rang — ce sont ceux qu'on ouvre à l'arrêt,
/// pas ceux qu'on utilise au volant.
class ChauffeurShell extends ConsumerStatefulWidget {
  const ChauffeurShell({super.key});

  @override
  ConsumerState<ChauffeurShell> createState() => _ChauffeurShellState();
}

class _ChauffeurShellState extends ConsumerState<ChauffeurShell> {
  static const _titres = [
    'Ma tournée',
    'Ma carte',
    'Messagerie',
    'Mes incidents',
  ];
  static const _idxMessages = 2;

  int _index = 0;
  int _nonLus = 0;
  Timer? _timerNonLus;

  @override
  void initState() {
    super.initState();
    // Démarrage de la vidange de la file : c'est ici, et nulle part ailleurs,
    // que les écritures différées repartent. Le provider est disposé par
    // Riverpod, on ne le libère donc pas à la main.
    ref.read(outboxSyncProvider).start();
    _chargerNonLus();
    _timerNonLus = Timer.periodic(Env.pollUnread, (_) => _chargerNonLus());
  }

  @override
  void dispose() {
    _timerNonLus?.cancel();
    super.dispose();
  }

  Future<void> _chargerNonLus() async {
    try {
      final n = await ref.read(apiProvider).getUnreadCount();
      if (mounted) setState(() => _nonLus = n);
    } catch (_) {
      // Réseau instable : on garde le compteur précédent plutôt que de le
      // remettre à zéro (un badge qui disparaît ment plus qu'un badge périmé).
    }
  }

  void _ouvrir(Widget page) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  Future<void> _deconnexion() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Se déconnecter ?'),
        content: const Text(
          'Vous devrez ressaisir vos identifiants pour reprendre une tournée.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Se déconnecter'),
          ),
        ],
      ),
    );
    if (ok == true) await ref.read(authProvider.notifier).logout();
  }

  void _ouvrirPlus() {
    final user = ref.read(authProvider);
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const CircleAvatar(
                child: Icon(Icons.person_outline_rounded),
              ),
              title: Text(user?.nom ?? 'Chauffeur'),
              subtitle: Text(user?.email ?? ''),
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.schedule_rounded),
              title: const Text('Prévisions ETA'),
              subtitle: const Text('heure de passage estimée par arrêt'),
              onTap: () {
                Navigator.pop(sheetContext);
                _ouvrir(const EtaScreen());
              },
            ),
            ListTile(
              leading: const Icon(Icons.notifications_none_rounded),
              title: const Text('Mes notifications'),
              onTap: () {
                Navigator.pop(sheetContext);
                _ouvrir(const NotificationsScreen());
              },
            ),
            ListTile(
              leading: const Icon(Icons.history_rounded),
              title: const Text('Mes trajets'),
              subtitle: const Text('historique'),
              onTap: () {
                Navigator.pop(sheetContext);
                _ouvrir(const HistoriqueScreen());
              },
            ),
            const Divider(),
            ListTile(
              leading: Icon(
                Theme.of(context).brightness == Brightness.dark
                    ? Icons.light_mode_outlined
                    : Icons.dark_mode_outlined,
              ),
              title: const Text('Changer de thème'),
              onTap: () {
                ref
                    .read(themeModeProvider.notifier)
                    .toggle(Theme.of(context).brightness);
                Navigator.pop(sheetContext);
              },
            ),
            ListTile(
              leading: const Icon(
                Icons.logout_rounded,
                color: AppColors.danger,
              ),
              title: const Text(
                'Se déconnecter',
                style: TextStyle(color: AppColors.danger),
              ),
              onTap: () {
                Navigator.pop(sheetContext);
                _deconnexion();
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_titres[_index]),
        actions: const [
          OutboxPill(),
          SizedBox(width: AppSpacing.xs),
        ],
      ),
      body: IndexedStack(
        index: _index,
        children: const [
          TourneeScreen(),
          MapScreen(),
          MessagesScreen(),
          IncidentsScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) {
          if (i == 4) {
            _ouvrirPlus();
            return; // « Plus » n'est pas une destination, c'est un menu
          }
          setState(() => _index = i);
          if (i == _idxMessages) _chargerNonLus();
        },
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.alt_route_outlined),
            selectedIcon: Icon(Icons.alt_route_rounded),
            label: 'Tournée',
          ),
          const NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map_rounded),
            label: 'Carte',
          ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: _nonLus > 0,
              label: Text('$_nonLus'),
              child: const Icon(Icons.forum_outlined),
            ),
            selectedIcon: Badge(
              isLabelVisible: _nonLus > 0,
              label: Text('$_nonLus'),
              child: const Icon(Icons.forum_rounded),
            ),
            label: 'Messages',
          ),
          const NavigationDestination(
            icon: Icon(Icons.warning_amber_outlined),
            selectedIcon: Icon(Icons.warning_amber_rounded),
            label: 'Incidents',
          ),
          const NavigationDestination(
            icon: Icon(Icons.more_horiz_rounded),
            label: 'Plus',
          ),
        ],
      ),
    );
  }
}
