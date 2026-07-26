import 'dart:async';

import 'package:flutter/material.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<NotificationItem>? _items;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(Env.pollInbox, (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    try {
      final items = await Api.instance.getMesNotifications();
      if (mounted) {
        setState(() {
          _items = items;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted && !silent) setState(() => _error = friendlyError(e));
    }
  }

  ({Color color, IconData icon}) _style(String type) {
    switch (type) {
      case 'INCIDENT_RESOLU':
      case 'ENFANT_A_BORD':
      case 'BUS_ARRIVE_ECOLE':
        return (color: AppColors.ok, icon: Icons.check_circle);
      case 'INCIDENT_SIGNALE':
      case 'RETARD':
        return (color: AppColors.danger, icon: Icons.warning_amber);
      case 'BUS_EN_ROUTE':
      case 'ENFANT_DEPOSE':
        return (color: AppColors.route, icon: Icons.directions_bus);
      default:
        return (color: AppColors.inkSoft, icon: Icons.notifications);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_items == null && _error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _items == null) {
      return ErrorRetry(message: _error!, onRetry: _load);
    }
    final items = _items ?? const [];
    if (items.isEmpty) {
      return const EmptyState(
          icon: Icons.notifications_off_outlined,
          text: 'Aucune notification pour le moment.');
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: items.length,
        itemBuilder: (context, i) {
          final n = items[i];
          final s = _style(n.type);
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: s.color.withValues(alpha: 0.12),
                    child: Icon(s.icon, color: s.color, size: 18),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                n.titre ?? n.type,
                                style: const TextStyle(fontWeight: FontWeight.w600),
                              ),
                            ),
                            Text(formatDateFr(n.dateEnvoi),
                                style: const TextStyle(
                                    fontSize: 11, color: AppColors.inkSoft)),
                          ],
                        ),
                        if (n.message != null && n.message!.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(n.message!,
                              style: const TextStyle(
                                  fontSize: 13, color: AppColors.inkSoft)),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
