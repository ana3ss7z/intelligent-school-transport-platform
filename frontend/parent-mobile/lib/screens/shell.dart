import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'assistant_screen.dart';
import 'home_screen.dart';
import 'map_screen.dart';
import 'messages_screen.dart';
import 'notifications_screen.dart';

class ParentShell extends ConsumerStatefulWidget {
  const ParentShell({super.key});

  @override
  ConsumerState<ParentShell> createState() => _ParentShellState();
}

class _ParentShellState extends ConsumerState<ParentShell> {
  int _index = 0;
  int _unread = 0;
  Timer? _unreadTimer;

  static const _titles = [
    'Mon espace',
    'Carte de mon enfant',
    'Messagerie',
    'Notifications',
    'Assistant',
  ];

  @override
  void initState() {
    super.initState();
    _pollUnread();
    _unreadTimer = Timer.periodic(Env.pollUnread, (_) => _pollUnread());
  }

  @override
  void dispose() {
    _unreadTimer?.cancel();
    super.dispose();
  }

  Future<void> _pollUnread() async {
    try {
      final n = await Api.instance.getUnreadCount();
      if (mounted) setState(() => _unread = n);
    } catch (_) {/* silencieux */}
  }

  Future<void> _confirmLogout() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Déconnexion'),
        content: const Text('Voulez-vous vous déconnecter ?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Annuler')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Déconnexion')),
        ],
      ),
    );
    if (ok == true) {
      await ref.read(authProvider.notifier).logout();
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(_titles[_index]),
        actions: [
          IconButton(
            tooltip: 'Déconnexion',
            icon: const Icon(Icons.logout),
            onPressed: _confirmLogout,
          ),
        ],
      ),
      body: IndexedStack(
        index: _index,
        children: const [
          HomeScreen(),
          MapScreen(),
          MessagesScreen(),
          NotificationsScreen(),
          AssistantScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) {
          setState(() => _index = i);
          if (i == 2) _pollUnread(); // rafraîchit le badge en ouvrant la messagerie
        },
        destinations: [
          const NavigationDestination(
              icon: Icon(Icons.dashboard_outlined),
              selectedIcon: Icon(Icons.dashboard),
              label: 'Accueil'),
          const NavigationDestination(
              icon: Icon(Icons.map_outlined),
              selectedIcon: Icon(Icons.map),
              label: 'Carte'),
          NavigationDestination(
            icon: _badge(const Icon(Icons.message_outlined)),
            selectedIcon: _badge(const Icon(Icons.message)),
            label: 'Messages',
          ),
          const NavigationDestination(
              icon: Icon(Icons.notifications_outlined),
              selectedIcon: Icon(Icons.notifications),
              label: 'Notifs'),
          const NavigationDestination(
              icon: Icon(Icons.auto_awesome_outlined),
              selectedIcon: Icon(Icons.auto_awesome),
              label: 'Assistant'),
        ],
      ),
      drawer: user == null ? null : _AccountDrawer(nom: user.nom, email: user.email),
    );
  }

  Widget _badge(Widget icon) {
    if (_unread <= 0) return icon;
    return Badge(
      label: Text('$_unread'),
      backgroundColor: AppColors.danger,
      child: icon,
    );
  }
}

class _AccountDrawer extends StatelessWidget {
  final String nom;
  final String email;
  const _AccountDrawer({required this.nom, required this.email});

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            UserAccountsDrawerHeader(
              decoration: const BoxDecoration(color: AppColors.route),
              accountName: Text(nom),
              accountEmail: Text(email),
              currentAccountPicture: CircleAvatar(
                backgroundColor: Colors.white,
                child: Text(
                  nom.isNotEmpty ? nom[0].toUpperCase() : 'P',
                  style: const TextStyle(
                      color: AppColors.route, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
