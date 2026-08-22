import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../theme.dart';

/// Date ISO backend (`2026-07-26T10:30:00`) → texte relatif court, sinon date.
String formatDateFr(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  try {
    final dt = DateTime.parse(iso);
    final diff = DateTime.now().difference(dt);
    if (diff.inSeconds < 60) return 'à l\'instant';
    if (diff.inMinutes < 60) return 'il y a ${diff.inMinutes} min';
    if (diff.inHours < 24) return 'il y a ${diff.inHours} h';
    if (diff.inDays == 1) return 'hier ${DateFormat('HH:mm').format(dt)}';
    return DateFormat('d MMM HH:mm', 'fr_FR').format(dt);
  } catch (_) {
    return iso;
  }
}

/// Étiquette colorée compacte, theme-aware.
class Chip2 extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  const Chip2(this.label, {super.key, this.color = AppColors.route, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.13),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 13, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

/// Tuile de statistique (icône + valeur + libellé).
class StatTile extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  const StatTile({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      // Lu d'un bloc par les lecteurs d'écran : « 3, Mes enfants ».
      child: Semantics(
        label: '$value $label',
        excludeSemantics: true,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.13),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, color: color, size: 20),
                ),
                const SizedBox(height: 8),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  label,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 11, color: context.softColor),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// En-tête de section.
class SectionHeader extends StatelessWidget {
  final String title;
  final Widget? trailing;
  const SectionHeader(this.title, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md, top: AppSpacing.xs),
      child: Row(
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          ),
          const Spacer(),
          ?trailing,
        ],
      ),
    );
  }
}

/// État vide générique.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String text;
  const EmptyState({super.key, required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: context.softColor.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 40, color: context.softColor),
            ),
            const SizedBox(height: 14),
            Text(
              text,
              textAlign: TextAlign.center,
              style: TextStyle(color: context.softColor),
            ),
          ],
        ),
      ),
    );
  }
}

/// Erreur avec bouton réessayer.
class ErrorRetry extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const ErrorRetry({super.key, required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.wifi_off_rounded,
              size: 40,
              color: AppColors.danger,
            ),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(color: context.softColor),
            ),
            const SizedBox(height: 14),
            FilledButton.tonalIcon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Réessayer'),
            ),
          ],
        ),
      ),
    );
  }
}

Color busStatusColor(String statut) {
  switch (statut.toUpperCase()) {
    case 'ACTIF':
      return AppColors.ok;
    case 'EN_PANNE':
      return AppColors.danger;
    default:
      return AppColors.inkSoft;
  }
}

/// Bloc gris animé (shimmer) pour les chargements.
class Skeleton extends StatefulWidget {
  final double? width;
  final double height;
  final BorderRadius? radius;
  const Skeleton({super.key, this.width, this.height = 14, this.radius});

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final base = context.borderColor;
    final highlight = context.softColor.withValues(alpha: 0.12);
    // Purement décoratif : masqué aux lecteurs d'écran.
    return ExcludeSemantics(
      child: RepaintBoundary(
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            return Container(
              width: widget.width,
              height: widget.height,
              decoration: BoxDecoration(
                borderRadius:
                    widget.radius ?? BorderRadius.circular(AppRadius.sm),
                gradient: LinearGradient(
                  begin: Alignment(-1 - 2 * _c.value, 0),
                  end: Alignment(1 - 2 * _c.value, 0),
                  colors: [base, highlight, base],
                  stops: const [0.35, 0.5, 0.65],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

/// Liste de cartes squelettes pour l'état de chargement.
class SkeletonCards extends StatelessWidget {
  final int count;
  const SkeletonCards({super.key, this.count = 3});

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      // Indispensable : ce squelette est parfois posé DANS un autre ListView
      // (écran ETA). Sans `shrinkWrap`, le viewport interne reçoit une hauteur
      // infinie, la passe de layout échoue, et les RenderBox ne sont jamais
      // dimensionnés → plus aucun hit-test ne passe : l'écran s'affiche mais
      // devient totalement insensible aux clics.
      // Le coût est nul ici (2 à 4 cartes fixes, rien à construire en flux) et
      // le défilement reste possible quand les contraintes sont bornées.
      shrinkWrap: true,
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: count,
      itemBuilder: (context, i) => const Padding(
        padding: EdgeInsets.only(bottom: AppSpacing.md),
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Skeleton(width: 160, height: 16),
                SizedBox(height: 12),
                Skeleton(width: 100, height: 12),
                SizedBox(height: 16),
                Skeleton(
                  height: 36,
                  radius: BorderRadius.all(Radius.circular(10)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
