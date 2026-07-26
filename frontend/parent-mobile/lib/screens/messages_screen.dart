import 'dart:async';

import 'package:flutter/material.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  List<MessageItem>? _items;
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
      final items = await Api.instance.getParentInbox();
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
          icon: Icons.mark_email_read_outlined,
          text: 'Aucun message reçu pour le moment.');
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: items.length,
        itemBuilder: (context, i) {
          final m = items[i];
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Chip2('Chauffeur',
                          color: AppColors.route, icon: Icons.directions_bus),
                      const Spacer(),
                      Text(formatDateFr(m.dateEnvoi),
                          style: const TextStyle(
                              fontSize: 11, color: AppColors.inkSoft)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(m.contenu),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
