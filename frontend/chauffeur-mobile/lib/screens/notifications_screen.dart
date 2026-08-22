import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Notifications reçues par le chauffeur (incident résolu sur son bus,
/// messages de l'administration, cycle de ses trajets).
class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  List<NotificationItem> _items = const [];
  bool _chargement = true;
  String? _erreur;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _charger());
    _timer = Timer.periodic(Env.pollInbox, (_) => _charger(silencieux: true));
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _charger({bool silencieux = false}) async {
    try {
      final liste = await ref.read(apiProvider).getMesNotifications();
      if (!mounted) return;
      setState(() {
        _items = liste;
        _chargement = false;
        _erreur = null;
      });
    } catch (e) {
      if (!mounted) return;
      if (!silencieux) {
        setState(() {
          _chargement = false;
          _erreur = friendlyError(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mes notifications')),
      body: _chargement
          ? const SkeletonCards(count: 4)
          : _erreur != null
          ? ErrorRetry(message: _erreur!, onRetry: _charger)
          : _items.isEmpty
          ? const EmptyState(
              icon: Icons.notifications_none_rounded,
              text: 'Aucune notification.',
            )
          : RefreshIndicator(
              onRefresh: _charger,
              child: ListView.builder(
                padding: const EdgeInsets.all(AppSpacing.lg),
                itemCount: _items.length,
                itemBuilder: (context, i) =>
                    _Ligne(key: ValueKey(_items[i].id), item: _items[i]),
              ),
            ),
    );
  }
}

class _Ligne extends StatelessWidget {
  const _Ligne({super.key, required this.item});
  final NotificationItem item;

  @override
  Widget build(BuildContext context) {
    final (couleur, icone) = _style(item.type);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: couleur.withValues(alpha: 0.13),
                  shape: BoxShape.circle,
                ),
                child: Icon(icone, size: 18, color: couleur),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.titre ?? item.type.replaceAll('_', ' '),
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    if ((item.message ?? '').isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(item.message!),
                    ],
                    const SizedBox(height: 6),
                    Text(
                      formatDateFr(item.dateEnvoi),
                      style: TextStyle(
                        fontSize: 11.5,
                        color: context.softColor,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static (Color, IconData) _style(String type) => switch (type.toUpperCase()) {
    'INCIDENT_RESOLU' => (AppColors.ok, Icons.check_circle_outline),
    'INCIDENT_SIGNALE' => (AppColors.danger, Icons.warning_amber_rounded),
    'MESSAGE_ADMIN' => (AppColors.route, Icons.forum_outlined),
    'TRAJET_DEMARRE' => (AppColors.route, Icons.play_circle_outline),
    'TRAJET_TERMINE' => (AppColors.inkSoft, Icons.flag_outlined),
    'ANOMALIE_DETECTEE' => (AppColors.danger, Icons.report_gmailerrorred),
    'RETARD' => (AppColors.warn, Icons.schedule_rounded),
    _ => (AppColors.inkSoft, Icons.notifications_none_rounded),
  };
}
