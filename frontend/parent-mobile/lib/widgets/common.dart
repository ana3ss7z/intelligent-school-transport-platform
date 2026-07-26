import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../theme.dart';

/// Formate une date ISO backend (`2026-07-26T10:30:00`) en `26 juil. 10:30`.
String formatDateFr(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  try {
    final dt = DateTime.parse(iso);
    return DateFormat('d MMM HH:mm', 'fr_FR').format(dt);
  } catch (_) {
    return iso;
  }
}

/// Petite étiquette colorée.
class Chip2 extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  const Chip2(this.label, {super.key, this.color = AppColors.route, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
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
            style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

/// État vide générique (icône + texte).
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
            Icon(icon, size: 44, color: AppColors.inkSoft.withValues(alpha: 0.5)),
            const SizedBox(height: 12),
            Text(
              text,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.inkSoft),
            ),
          ],
        ),
      ),
    );
  }
}

/// Affiche une erreur avec bouton réessayer.
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
            const Icon(Icons.wifi_off, size: 40, color: AppColors.danger),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: onRetry, child: const Text('Réessayer')),
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
