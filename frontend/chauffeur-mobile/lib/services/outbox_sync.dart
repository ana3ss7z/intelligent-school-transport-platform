import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';

import '../config/env.dart';
import 'outbox.dart';

/// Décide *quand* vider la file. La file elle-même ne sait pas ce qu'est le
/// réseau — c'est ce qui la rend testable sans plugin.
///
/// Trois déclencheurs, volontairement redondants :
///  1. retour de connectivité (le signal le plus rapide) ;
///  2. reprise de l'app au premier plan (le chauffeur rouvre son téléphone) ;
///  3. un balayage périodique, filet de sécurité — `connectivity_plus` signale
///     qu'une interface est *montée*, pas qu'internet est *joignable* (portail
///     captif, Wi-Fi du garage sans route). Sans ce timer, une file pourrait
///     rester bloquée alors que la connexion est revenue en silence.
class OutboxSync with WidgetsBindingObserver {
  OutboxSync(this._outbox);

  final Outbox _outbox;
  StreamSubscription<List<ConnectivityResult>>? _connSub;
  Timer? _timer;

  void start() {
    WidgetsBinding.instance.addObserver(this);
    _connSub = Connectivity().onConnectivityChanged.listen((results) {
      final enLigne = results.any((r) => r != ConnectivityResult.none);
      if (enLigne) unawaited(_outbox.drain());
    });
    _timer = Timer.periodic(Env.outboxSweep, (_) => unawaited(_outbox.drain()));
    unawaited(_outbox.drain());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_outbox.drain());
  }

  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _connSub?.cancel();
    _timer?.cancel();
  }
}
