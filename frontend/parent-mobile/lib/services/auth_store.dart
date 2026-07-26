import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/models.dart';

/// Persistance chiffrée de la session (JWT + utilisateur).
class AuthStore {
  static const _kUser = 'ts_auth';
  final _storage = const FlutterSecureStorage();

  Future<AuthUser?> load() async {
    final raw = await _storage.read(key: _kUser);
    if (raw == null) return null;
    try {
      return AuthUser.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      await clear();
      return null;
    }
  }

  Future<void> save(AuthUser user) async {
    await _storage.write(key: _kUser, value: jsonEncode(user.toJson()));
  }

  Future<void> clear() async {
    await _storage.delete(key: _kUser);
  }
}
