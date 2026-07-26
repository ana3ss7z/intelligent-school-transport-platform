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
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
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
      // Historique borné aux 8 derniers tours (le back borne aussi).
      final history = _msgs.length > 8 ? _msgs.sublist(_msgs.length - 8) : List<ChatTurn>.from(_msgs);
      final reply = await Api.instance.chat(message, history);
      setState(() => _msgs.add(ChatTurn(
          'assistant', reply.reply.isEmpty ? '…' : reply.reply)));
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
        Expanded(
          child: _msgs.isEmpty ? _empty() : _list(),
        ),
        if (_busy) const _TypingIndicator(),
        _composer(),
      ],
    );
  }

  Widget _empty() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const SizedBox(height: 20),
        const Icon(Icons.auto_awesome, size: 48, color: AppColors.route),
        const SizedBox(height: 12),
        const Text(
          'Assistant transport',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        const Text(
          'Je peux vous renseigner sur la position du bus, l\'heure d\'arrivée, '
          'la présence de votre enfant et les incidents.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.inkSoft),
        ),
        const SizedBox(height: 24),
        ..._suggestions.map((s) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: OutlinedButton(
                onPressed: () => _send(s),
                style: OutlinedButton.styleFrom(
                  alignment: Alignment.centerLeft,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                child: Text(s, textAlign: TextAlign.left),
              ),
            )),
      ],
    );
  }

  Widget _list() {
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.all(12),
      itemCount: _msgs.length,
      itemBuilder: (context, i) => _Bubble(turn: _msgs[i]),
    );
  }

  Widget _composer() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: Color(0xFFE2E8F0))),
        ),
        child: Row(
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
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                ),
              ),
            ),
            const SizedBox(width: 8),
            FloatingActionButton.small(
              heroTag: 'send',
              backgroundColor: AppColors.route,
              foregroundColor: Colors.white,
              onPressed: _busy ? null : () => _send(_input.text),
              child: const Icon(Icons.send),
            ),
          ],
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
            maxWidth: MediaQuery.of(context).size.width * 0.78),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isUser ? AppColors.route : Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: isUser ? null : Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: Text(
          turn.content,
          style: TextStyle(color: isUser ? Colors.white : const Color(0xFF0F172A)),
        ),
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(left: 20, bottom: 6),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2)),
            SizedBox(width: 8),
            Text('L\'assistant réfléchit…',
                style: TextStyle(color: AppColors.inkSoft, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}
