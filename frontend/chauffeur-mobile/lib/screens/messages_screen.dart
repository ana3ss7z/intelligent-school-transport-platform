import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../services/outbox.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Messagerie chauffeur — **bidirectionnelle**, contrairement à l'app parent.
///
/// Deux canaux distincts :
///  · le fil avec l'administration (`/api/messages`, conversation unique) ;
///  · la diffusion aux parents du groupe (`/api/messages/diffusion?busId=`),
///    volontairement isolée du fil pour qu'un « je suis en retard » destiné aux
///    familles ne parte jamais par erreur à l'administration, et inversement.
class MessagesScreen extends ConsumerStatefulWidget {
  const MessagesScreen({super.key});

  @override
  ConsumerState<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends ConsumerState<MessagesScreen> {
  final _saisie = TextEditingController();
  final _scroll = ScrollController();

  List<MessageItem> _messages = const [];
  bool _chargement = true;
  bool _envoi = false;
  String? _erreur;
  Timer? _timer;

  /// Id local décroissant pour les messages optimistes, jamais confondu avec
  /// un id serveur (toujours positif).
  int _prochainIdLocal = -1;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _charger());
    _timer = Timer.periodic(
      Env.pollConversation,
      (_) => _charger(silencieux: true),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    _saisie.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _charger({bool silencieux = false}) async {
    try {
      final liste = await ref.read(apiProvider).getMaConversation();
      if (!mounted) return;
      // Les messages locaux non confirmés survivent au rafraîchissement, sinon
      // ils clignoteraient hors de la liste à chaque sondage.
      final locaux = _messages.where((m) => m.enAttente || m.echec).toList();
      setState(() {
        _messages = [...liste, ...locaux];
        _chargement = false;
        _erreur = null;
      });
      _versLeBas();
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

  void _versLeBas() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: AppDurations.medium,
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _envoyer() async {
    final texte = _saisie.text.trim();
    if (texte.isEmpty || _envoi) return;

    final idLocal = _prochainIdLocal--;
    setState(() {
      _envoi = true;
      _saisie.clear();
      _messages = [
        ..._messages,
        MessageItem(
          id: idLocal,
          expediteurRole: 'CHAUFFEUR',
          contenu: texte,
          dateEnvoi: DateTime.now().toIso8601String(),
          enAttente: true,
        ),
      ];
    });
    _versLeBas();

    try {
      await ref.read(apiProvider).envoyerMessage(texte);
      if (!mounted) return;
      setState(() => _messages.removeWhere((m) => m.id == idLocal));
      await _charger(silencieux: true);
    } catch (e) {
      if (!mounted) return;
      if (isOffline(e)) {
        await ref.read(outboxProvider).enqueue(OutboxKind.message, {
          'contenu': texte,
        });
        // La bulle reste, marquée « en attente » : le message n'est pas perdu,
        // il est juste en file.
      } else {
        setState(() {
          _messages = [
            for (final m in _messages)
              if (m.id == idLocal)
                MessageItem(
                  id: m.id,
                  expediteurRole: m.expediteurRole,
                  contenu: m.contenu,
                  dateEnvoi: m.dateEnvoi,
                  echec: true,
                )
              else
                m,
          ];
        });
      }
    } finally {
      if (mounted) setState(() => _envoi = false);
    }
  }

  Future<void> _reessayer(MessageItem m) async {
    setState(() => _messages.removeWhere((x) => x.id == m.id));
    _saisie.text = m.contenu;
    await _envoyer();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: _chargement
              ? const SkeletonCards(count: 4)
              : _erreur != null
              ? ErrorRetry(message: _erreur!, onRetry: _charger)
              : _messages.isEmpty
              ? const EmptyState(
                  icon: Icons.forum_outlined,
                  text: 'Aucun message.\nDémarrez la conversation.',
                )
              : RefreshIndicator(
                  onRefresh: _charger,
                  child: ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) => _Bulle(
                      key: ValueKey(_messages[i].id),
                      message: _messages[i],
                      onRetry: () => _reessayer(_messages[i]),
                    ),
                  ),
                ),
        ),
        const _BarreDiffusion(),
        _Composeur(controller: _saisie, envoi: _envoi, onEnvoyer: _envoyer),
      ],
    );
  }
}

class _Bulle extends StatelessWidget {
  const _Bulle({super.key, required this.message, required this.onRetry});
  final MessageItem message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final aMoi = (message.expediteurRole ?? '') == 'CHAUFFEUR';
    final fond = aMoi ? AppColors.route : context.borderColor;
    final encre = aMoi ? Colors.white : null;

    return Align(
      alignment: aMoi ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.78,
        ),
        margin: const EdgeInsets.only(bottom: AppSpacing.sm),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: message.echec
              ? AppColors.danger.withValues(alpha: 0.15)
              : fond,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(AppRadius.md),
            topRight: const Radius.circular(AppRadius.md),
            bottomLeft: Radius.circular(aMoi ? AppRadius.md : 4),
            bottomRight: Radius.circular(aMoi ? 4 : AppRadius.md),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!aMoi && (message.expediteurNom ?? '').isNotEmpty)
              Text(
                message.expediteurNom!,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: context.softColor,
                ),
              ),
            Text(message.contenu, style: TextStyle(color: encre)),
            const SizedBox(height: 3),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (message.echec) ...[
                  const Icon(
                    Icons.error_outline_rounded,
                    size: 13,
                    color: AppColors.danger,
                  ),
                  const SizedBox(width: 4),
                  const Text(
                    'non envoyé',
                    style: TextStyle(fontSize: 11, color: AppColors.danger),
                  ),
                  const SizedBox(width: 6),
                  InkWell(
                    onTap: onRetry,
                    child: const Text(
                      'Réessayer',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: AppColors.danger,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                  ),
                ] else if (message.enAttente) ...[
                  Icon(
                    Icons.schedule_rounded,
                    size: 12,
                    color: encre?.withValues(alpha: 0.75) ?? context.softColor,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'en attente',
                    style: TextStyle(
                      fontSize: 11,
                      color:
                          encre?.withValues(alpha: 0.75) ?? context.softColor,
                    ),
                  ),
                ] else
                  Text(
                    formatDateFr(message.dateEnvoi),
                    style: TextStyle(
                      fontSize: 11,
                      color:
                          encre?.withValues(alpha: 0.75) ?? context.softColor,
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Composeur extends StatelessWidget {
  const _Composeur({
    required this.controller,
    required this.envoi,
    required this.onEnvoyer,
  });

  final TextEditingController controller;
  final bool envoi;
  final VoidCallback onEnvoyer;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          border: Border(top: BorderSide(color: context.borderColor)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onEnvoyer(),
                decoration: const InputDecoration(
                  hintText: 'Message à l\'administration…',
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            IconButton.filled(
              onPressed: envoi ? null : onEnvoyer,
              icon: const Icon(Icons.send_rounded, size: 20),
              tooltip: 'Envoyer',
            ),
          ],
        ),
      ),
    );
  }
}

/// Diffusion aux parents du groupe — un canal, un bouton, aucune ambiguïté.
class _BarreDiffusion extends ConsumerStatefulWidget {
  const _BarreDiffusion();

  @override
  ConsumerState<_BarreDiffusion> createState() => _BarreDiffusionState();
}

class _BarreDiffusionState extends ConsumerState<_BarreDiffusion> {
  /// Possédé par l'état, pas créé dans `_ouvrir()` : la feuille continue de se
  /// reconstruire pendant son animation de fermeture, donc un contrôleur libéré
  /// juste après le `await` serait réutilisé après `dispose()`.
  final _texte = TextEditingController();

  @override
  void dispose() {
    _texte.dispose();
    super.dispose();
  }

  Future<void> _ouvrir() async {
    final bus = ref.read(myBusProvider).value;
    if (bus == null) return;
    _texte.clear();
    var envoi = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.only(
          left: AppSpacing.lg,
          right: AppSpacing.lg,
          bottom: MediaQuery.viewInsetsOf(sheetContext).bottom + AppSpacing.lg,
        ),
        child: StatefulBuilder(
          builder: (sheetContext, setSheetState) => Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Diffusion aux parents',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 4),
              Text(
                'Envoyé à tous les parents du bus ${bus.matricule}. '
                'Ce message n\'apparaît pas dans votre fil avec l\'administration.',
                style: TextStyle(fontSize: 12.5, color: context.softColor),
              ),
              const SizedBox(height: AppSpacing.lg),
              TextField(
                controller: _texte,
                maxLines: 3,
                autofocus: true,
                decoration: const InputDecoration(
                  hintText: 'Ex. Léger retard ce matin, ~10 min.',
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: envoi
                      ? null
                      : () async {
                          final texte = _texte.text.trim();
                          if (texte.isEmpty) return;
                          setSheetState(() => envoi = true);
                          final messenger = ScaffoldMessenger.of(context);
                          try {
                            final n = await ref
                                .read(apiProvider)
                                .diffuserAuxParents(bus.id, texte);
                            if (sheetContext.mounted) {
                              Navigator.pop(sheetContext);
                            }
                            messenger.showSnackBar(
                              SnackBar(
                                content: Text('Diffusé à $n parent(s).'),
                              ),
                            );
                          } catch (e) {
                            if (isOffline(e)) {
                              await ref.read(outboxProvider).enqueue(
                                OutboxKind.diffusion,
                                {'busId': bus.id, 'contenu': texte},
                              );
                              if (sheetContext.mounted) {
                                Navigator.pop(sheetContext);
                              }
                              messenger.showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'Hors ligne — la diffusion partira au '
                                    'retour du réseau',
                                  ),
                                ),
                              );
                            } else {
                              setSheetState(() => envoi = false);
                              messenger.showSnackBar(
                                SnackBar(
                                  content: Text(friendlyError(e)),
                                  backgroundColor: AppColors.danger,
                                ),
                              );
                            }
                          }
                        },
                  icon: const Icon(Icons.campaign_outlined, size: 18),
                  label: Text(envoi ? 'Envoi…' : 'Diffuser aux parents'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bus = ref.watch(myBusProvider).value;
    if (bus == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      child: SizedBox(
        width: double.infinity,
        child: OutlinedButton.icon(
          onPressed: _ouvrir,
          icon: const Icon(Icons.campaign_outlined, size: 18),
          label: const Text('Diffuser un message aux parents'),
        ),
      ),
    );
  }
}
