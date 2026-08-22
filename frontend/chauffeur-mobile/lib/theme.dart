import 'package:flutter/material.dart';

/// Accents de marque — lisibles en clair ET en sombre (couleurs saturées).
/// Les surfaces/textes viennent du ColorScheme (theme-aware) ; ceci = accents sémantiques.
class AppColors {
  static const brand = Color(0xFF2563EB); // bleu principal (route)
  static const route = Color(0xFF2563EB);
  static const ok = Color(0xFF16A34A); // à bord / résolu
  static const warn = Color(0xFFF59E0B); // en route / retard
  static const danger = Color(0xFFDC2626); // incident / hors ligne
  static const inkSoft = Color(0xFF64748B); // texte secondaire (fallback)

  /// Accent propre à l'espace chauffeur (marque de connexion, émission GPS,
  /// icône de l'app). Le bleu reste la couleur du produit ; ce teal sert à
  /// distinguer cette app de l'app parent sur un même téléphone.
  static const driver = Color(0xFF0F766E);
}

/// Tokens d'espacement (grille 4/8 pt) et de rayon — cohérence visuelle.
class AppSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
}

class AppRadius {
  static const double sm = 10;
  static const double md = 14;
  static const double lg = 18;
  static const double pill = 999;
}

class AppDurations {
  static const fast = Duration(milliseconds: 180);
  static const medium = Duration(milliseconds: 280);
  static const slow = Duration(milliseconds: 500);
}

ThemeData buildTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final scheme = ColorScheme.fromSeed(
    seedColor: AppColors.brand,
    brightness: brightness,
  );

  final scaffoldBg = isDark ? const Color(0xFF0B1220) : const Color(0xFFF6F8FB);
  final cardColor = isDark ? const Color(0xFF161F30) : Colors.white;
  final borderColor = isDark
      ? const Color(0xFF273248)
      : const Color(0xFFE6EBF2);
  final appBarBg = isDark ? const Color(0xFF0F1826) : Colors.white;
  final onSurface = isDark ? const Color(0xFFE7ECF3) : const Color(0xFF0F172A);
  final onSurfaceSoft = isDark ? const Color(0xFF97A3B6) : AppColors.inkSoft;

  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme.copyWith(
      primary: AppColors.brand,
      surface: cardColor,
      onSurface: onSurface,
    ),
    scaffoldBackgroundColor: scaffoldBg,
  );

  return base.copyWith(
    textTheme: base.textTheme.apply(
      bodyColor: onSurface,
      displayColor: onSurface,
    ),
    appBarTheme: AppBarTheme(
      centerTitle: false,
      backgroundColor: appBarBg,
      foregroundColor: onSurface,
      elevation: 0,
      scrolledUnderElevation: 0.5,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: TextStyle(
        color: onSurface,
        fontSize: 19,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.2,
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: cardColor,
      surfaceTintColor: Colors.transparent,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        side: BorderSide(color: borderColor),
      ),
    ),
    dividerTheme: DividerThemeData(color: borderColor, thickness: 1, space: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: isDark ? const Color(0xFF0F1826) : Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
        borderSide: BorderSide(color: borderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
        borderSide: BorderSide(color: borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
        borderSide: const BorderSide(color: AppColors.brand, width: 2),
      ),
      hintStyle: TextStyle(color: onSurfaceSoft),
      labelStyle: TextStyle(color: onSurfaceSoft),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.brand,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 15, horizontal: 20),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: onSurface,
        side: BorderSide(color: borderColor),
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: appBarBg,
      surfaceTintColor: Colors.transparent,
      indicatorColor: AppColors.brand.withValues(alpha: 0.14),
      elevation: 0,
      height: 66,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      iconTheme: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return IconThemeData(
          color: selected ? AppColors.brand : onSurfaceSoft,
          size: 24,
        );
      }),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return TextStyle(
          fontSize: 11.5,
          fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          color: selected ? AppColors.brand : onSurfaceSoft,
        );
      }),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
    ),
    dialogTheme: DialogThemeData(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
    ),
    extensions: [
      AppSemanticColors(surfaceSoft: onSurfaceSoft, border: borderColor),
    ],
  );
}

/// Couleurs sémantiques dérivées, accessibles via Theme.of(context).extension.
@immutable
class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  final Color surfaceSoft; // texte secondaire
  final Color border;
  const AppSemanticColors({required this.surfaceSoft, required this.border});

  @override
  AppSemanticColors copyWith({Color? surfaceSoft, Color? border}) =>
      AppSemanticColors(
        surfaceSoft: surfaceSoft ?? this.surfaceSoft,
        border: border ?? this.border,
      );

  @override
  AppSemanticColors lerp(ThemeExtension<AppSemanticColors>? other, double t) {
    if (other is! AppSemanticColors) return this;
    return AppSemanticColors(
      surfaceSoft: Color.lerp(surfaceSoft, other.surfaceSoft, t)!,
      border: Color.lerp(border, other.border, t)!,
    );
  }
}

/// Raccourcis theme-aware.
extension ThemeX on BuildContext {
  ColorScheme get scheme => Theme.of(this).colorScheme;
  Color get softColor =>
      Theme.of(this).extension<AppSemanticColors>()?.surfaceSoft ??
      AppColors.inkSoft;
  Color get borderColor =>
      Theme.of(this).extension<AppSemanticColors>()?.border ??
      const Color(0xFFE6EBF2);
}
