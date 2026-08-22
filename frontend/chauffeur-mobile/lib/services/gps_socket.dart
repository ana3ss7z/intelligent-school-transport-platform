import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:latlong2/latlong.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as ws_status;

import '../config/env.dart';
import '../models/models.dart';

/// Connexion WebSocket GPS (MS3) — collecte toutes les positions BUS en direct.
///
/// S'abonne à `ALL` (le serveur ne garde qu'un seul filtre : pour plusieurs bus
/// on filtre côté client, comme le web). Reconnexion automatique, throttle ~1s,
/// trail des 25 derniers points par bus.
class GpsSocket extends ChangeNotifier {
  static const int _trailMax = 25;

  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;
  Timer? _flushTimer;
  bool _disposed = false;
  bool _dirty = false;

  bool connected = false;

  /// Dernière position par busId.
  final Map<int, GpsPosition> positions = {};

  /// Trail (LatLng) par busId.
  final Map<int, List<LatLng>> trails = {};

  /// [autoConnect] à false = objet inerte, pour les tests de widgets : sans ça
  /// chaque test ouvrirait une vraie WebSocket vers MS3 et laisserait derrière
  /// lui un timer de reconnexion.
  GpsSocket({bool autoConnect = true}) {
    if (autoConnect) _connect();
  }

  void _connect() {
    if (_disposed) return;
    try {
      final ch = WebSocketChannel.connect(Uri.parse(Env.wsGps));
      _channel = ch;
      _sub = ch.stream.listen(
        _onMessage,
        onDone: _onClosed,
        onError: (_) => _onClosed(),
        cancelOnError: true,
      );
      // Abonnement global ; filtrage des bus des enfants côté écran.
      ch.sink.add(jsonEncode({'subscribe': 'ALL'}));
      connected = true;
      _scheduleNotify();
    } catch (_) {
      _onClosed();
    }
  }

  void _onMessage(dynamic data) {
    if (_disposed) return;
    connected = true;
    try {
      final decoded = jsonDecode(data as String);
      if (decoded is! Map) return;
      // Frame de contrôle {"type":"subscribed",...} → ignorée.
      if (decoded['type'] == 'subscribed') return;
      if (decoded['cibleType'] != 'BUS' || decoded['cibleId'] == null) return;

      final pos = GpsPosition.fromJson(Map<String, dynamic>.from(decoded));
      positions[pos.cibleId] = pos;
      final trail = trails.putIfAbsent(pos.cibleId, () => <LatLng>[]);
      trail.add(LatLng(pos.latitude, pos.longitude));
      if (trail.length > _trailMax) trail.removeAt(0);
      _scheduleNotify();
    } catch (_) {
      // ping/message non-JSON → ignoré
    }
  }

  void _onClosed() {
    if (_disposed) return;
    connected = false;
    _scheduleNotify();
    _sub?.cancel();
    _sub = null;
    _channel = null;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(milliseconds: 2500), _connect);
  }

  /// Throttle les notifications à ~1 update/seconde (comme le web).
  void _scheduleNotify() {
    _dirty = true;
    _flushTimer ??= Timer(const Duration(seconds: 1), () {
      _flushTimer = null;
      if (_disposed) return;
      if (_dirty) {
        _dirty = false;
        notifyListeners();
      }
    });
  }

  @override
  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _flushTimer?.cancel();
    _sub?.cancel();
    try {
      _channel?.sink.close(ws_status.normalClosure);
    } catch (_) {}
    super.dispose();
  }
}
