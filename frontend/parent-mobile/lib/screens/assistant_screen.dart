import 'package:flutter/material.dart';

import '../api/api.dart';
import '../models/models.dart';
import '../theme.dart';

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<ChatTurn> _msgs = [];
  bool _busy = false;

  static const _suggestions = [
    'Où est le bus de mon enfant ?',
    'Dans combien de temps arrive-t-il à l\'école ?',
    'Mon enfant est-il monté dans le bus ?',
    'Y a-t-il un incident sur son bus ?',
  ];

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToEnd() {
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

  Future<void> _send(String text) async {
    final message = text.trim();
    if (message.isEmpty || _busy) return;
    setState(() {
      _msgs.add(ChatTurn('user', message));
      _busy = true;
      _input.clear();
    });
    _scrollToEnd();
    try {
      final history = _msgs.length > 8
          ? _msgs.sublist(_msgs.length - 8)
          : List<ChatTurn>.from(_msgs);
      final reply = await Api.instance.chat(message, history);
      setState(
        () => _msgs.add(
          ChatTurn('assistant', reply.reply.isEmpty ? '…' : reply.reply),
        ),
      );
    } catch (e) {
      setState(() => _msgs.add(ChatTurn('assistant', friendlyError(e))));
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollToEnd();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(child: _msgs.isEmpty ? _empty() : _list()),
        if (_busy) const _TypingDots(),
        _composer(context),
      ],
    );
  }

  Widget _empty() {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      children: [
        const SizedBox(height: AppSpacing.lg),
        Center(
          child: Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: AppColors.brand.withValues(alpha: 0.13),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.auto_awesome_rounded,
              size: 32,
              color: AppColors.brand,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        const Text(
          'Assistant transport',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        Text(
          'Je vous renseigne sur la position du bus, l\'heure d\'arrivée, '
          'la présence de votre enfant et les incidents.',
          textAlign: TextAlign.center,
          style: TextStyle(color: context.softColor, height: 1.4),
        ),
        const SizedBox(height: AppSpacing.xl),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          alignment: WrapAlignment.center,
          children: _suggestions
              .map(
                (s) => ActionChip(
                  label: Text(s),
                  onPressed: () => _send(s),
                  side: BorderSide(color: context.borderColor),
                  backgroundColor: context.scheme.surface,
                  labelStyle: const TextStyle(fontSize: 13),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                ),
              )
              .toList(),
        ),
      ],
    );
  }

  Widget _list() {
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: _msgs.length,
      itemBuilder: (context, i) => _Bubble(turn: _msgs[i]),
    );
  }

  Widget _composer(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: BoxDecoration(
          color: context.scheme.surface,
          border: Border(top: BorderSide(color: context.borderColor)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: _input,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: _send,
                decoration: const InputDecoration(
                  hintText: 'Posez votre question…',
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            _SendButton(busy: _busy, onTap: () => _send(_input.text)),
          ],
        ),
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  final bool busy;
  final VoidCallback onTap;
  const _SendButton({required this.busy, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Envoyer',
      child: Material(
        color: busy ? context.softColor : AppColors.brand,
        borderRadius: BorderRadius.circular(AppRadius.md),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.md),
          onTap: busy ? null : onTap,
          child: const SizedBox(
            width: 48,
            height: 48,
            child: Icon(Icons.send_rounded, color: Colors.white, size: 20),
          ),
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  final ChatTurn turn;
  const _Bubble({required this.turn});

  @override
  Widget build(BuildContext context) {
    final isUser = turn.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.80,
        ),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isUser ? AppColors.brand : context.scheme.surface,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(AppRadius.md),
            topRight: const Radius.circular(AppRadius.md),
            bottomLeft: Radius.circular(isUser ? AppRadius.md : 4),
            bottomRight: Radius.circular(isUser ? 4 : AppRadius.md),
          ),
          border: isUser ? null : Border.all(color: context.borderColor),
        ),
        child: Text(
          turn.content,
          style: TextStyle(
            height: 1.4,
            color: isUser ? Colors.white : context.scheme.onSurface,
          ),
        ),
      ),
    );
  }
}

class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1000),
  )..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(left: AppSpacing.lg, bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: context.scheme.surface,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: Border.all(color: context.borderColor),
        ),
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) => Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(3, (i) {
              final t = ((_c.value + i * 0.2) % 1.0);
              final o = 0.3 + 0.7 * (1 - (t - 0.5).abs() * 2).clamp(0.0, 1.0);
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2.5),
                child: Opacity(
                  opacity: o,
                  child: const CircleAvatar(
                    radius: 3.5,
                    backgroundColor: AppColors.brand,
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}
