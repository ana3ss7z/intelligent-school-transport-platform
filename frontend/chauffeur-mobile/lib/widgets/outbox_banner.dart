import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/outbox.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'common.dart';

/// Pastille « N action(s) en attente », posée dans l'AppBar du shell.
///
/// Elle rend visible la seule chose qu'un chauffeur ne peut pas deviner :
/// est-ce que ce que je viens de pointer est *vraiment* parti ? Silencieuse
/// quand la file est vide.
class OutboxPill extends ConsumerWidget {
  const OutboxPill({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outbox = ref.watch(outboxProvider);
    return ListenableBuilder(
      listenable: outbox,
      builder: (context, _) {
        final enAttente = outbox.pendingCount;
        final parkes = outbox.parkedCount;
        if (enAttente == 0 && parkes == 0) return const SizedBox.shrink();

        final couleur = parkes > 0 ? AppColors.danger : AppColors.warn;
        final total = enAttente + parkes;
        final libelle = parkes > 0
            ? '$parkes échec${parkes > 1 ? 's' : ''}'
            : '$enAttente en attente';

        return Semantics(
          button: true,
          label: parkes > 0
              ? '$parkes action non envoyée, appuyer pour traiter'
              : '$total action${total > 1 ? 's' : ''} en attente d\'envoi',
          child: Padding(
            padding: const EdgeInsets.only(right: AppSpacing.sm),
            child: InkWell(
              borderRadius: BorderRadius.circular(AppRadius.pill),
              onTap: () => showOutboxSheet(context, ref),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: couleur.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      parkes > 0
                          ? Icons.error_outline_rounded
                          : Icons.cloud_upload_outlined,
                      size: 15,
                      color: couleur,
                    ),
                    const SizedBox(width: 5),
                    Text(
                      libelle,
                      style: TextStyle(
                        color: couleur,
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Feuille détaillant la file : ce qui part tout seul, et ce qui attend une
/// décision du chauffeur.
Future<void> showOutboxSheet(BuildContext context, WidgetRef ref) {
  final outbox = ref.read(outboxProvider);
  return showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (context) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.55,
      maxChildSize: 0.9,
      builder: (context, scrollController) => ListenableBuilder(
        listenable: outbox,
        builder: (context, _) {
          final pending = outbox.pending;
          final parked = outbox.parked;
          return ListView(
            controller: scrollController,
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              0,
              AppSpacing.lg,
              AppSpacing.xl,
            ),
            children: [
              const Text(
                'Actions en attente',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 4),
              Text(
                'Elles partiront automatiquement au retour du réseau, dans '
                'l\'ordre où vous les avez faites.',
                style: TextStyle(color: context.softColor, fontSize: 13),
              ),
              const SizedBox(height: AppSpacing.lg),

              if (pending.isEmpty && parked.isEmpty)
                const EmptyState(
                  icon: Icons.cloud_done_outlined,
                  text: 'Tout est synchronisé.',
                ),

              for (final item in pending)
                _LigneOutbox(
                  item: item,
                  couleur: AppColors.warn,
                  icone: Icons.schedule_rounded,
                  sousTitre: item.attempts == 0
                      ? 'en attente d\'envoi'
                      : 'essai ${item.attempts} — ${item.lastError ?? ''}',
                ),

              if (parked.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.lg),
                Text(
                  'Non envoyées',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppColors.danger,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Après plusieurs échecs, ces actions ne repartent plus '
                  'seules : à vous de décider.',
                  style: TextStyle(color: context.softColor, fontSize: 12),
                ),
                const SizedBox(height: AppSpacing.sm),
                for (final item in parked)
                  _LigneOutbox(
                    item: item,
                    couleur: AppColors.danger,
                    icone: Icons.error_outline_rounded,
                    sousTitre: item.lastError ?? 'échec',
                    actions: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          tooltip: 'Réessayer',
                          icon: const Icon(Icons.refresh_rounded, size: 20),
                          onPressed: () => outbox.retryParked(item.id),
                        ),
                        IconButton(
                          tooltip: 'Abandonner',
                          icon: const Icon(Icons.delete_outline, size: 20),
                          onPressed: () => outbox.remove(item.id),
                        ),
                      ],
                    ),
                  ),
              ],
            ],
          );
        },
      ),
    ),
  );
}

class _LigneOutbox extends StatelessWidget {
  const _LigneOutbox({
    required this.item,
    required this.couleur,
    required this.icone,
    required this.sousTitre,
    this.actions,
  });

  final OutboxItem item;
  final Color couleur;
  final IconData icone;
  final String sousTitre;
  final Widget? actions;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          child: Row(
            children: [
              Icon(icone, size: 18, color: couleur),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.libelle,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    Text(
                      sousTitre,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 12, color: context.softColor),
                    ),
                  ],
                ),
              ),
              ?actions,
            ],
          ),
        ),
      ),
    );
  }
}
