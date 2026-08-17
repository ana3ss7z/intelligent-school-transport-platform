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
    if (_items == null && _error == null) return const SkeletonCards(count: 4);
    if (_error != null && _items == null) {
      return ErrorRetry(message: _error!, onRetry: _load);
    }
    final items = _items ?? const [];
    if (items.isEmpty) {
      return const EmptyState(
        icon: Icons.mark_email_read_outlined,
        text: 'Aucun message reçu pour le moment.',
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(AppSpacing.md),
        itemCount: items.length,
        itemBuilder: (context, i) {
          final m = items[i];
          return Padding(
            key: ValueKey(m.id),
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: Semantics(
              label:
                  'Message du chauffeur, ${formatDateFr(m.dateEnvoi)} : '
                  '${m.contenu}',
              excludeSemantics: true,
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      CircleAvatar(
                        radius: 18,
                        backgroundColor: AppColors.brand.withValues(
                          alpha: 0.13,
                        ),
                        child: const Icon(
                          Icons.directions_bus_rounded,
                          size: 18,
                          color: AppColors.brand,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Text(
                                  'Chauffeur',
                                  style: TextStyle(fontWeight: FontWeight.w700),
                                ),
                                const Spacer(),
                                Text(
                                  formatDateFr(m.dateEnvoi),
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: context.softColor,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 5),
                            Text(
                              m.contenu,
                              style: const TextStyle(height: 1.35),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
