import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:safezone_app/models/patrol_assignment.dart';
import 'package:safezone_app/models/user_profile.dart';

abstract interface class TokenStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> clear();
}

class SecureTokenStore implements TokenStore {
  const SecureTokenStore();
  static const _storage = FlutterSecureStorage(aOptions: AndroidOptions());
  static const _key = 'safezone_police_access_token';

  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String token) => _storage.write(key: _key, value: token);
  @override
  Future<void> clear() => _storage.delete(key: _key);
}

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({
    http.Client? client,
    TokenStore? tokenStore,
    String? baseUrl,
  })  : _client = client ?? http.Client(),
        _tokens = tokenStore ?? const SecureTokenStore(),
        baseUrl = (baseUrl ?? const String.fromEnvironment(
          'SAFEZONE_API_BASE_URL',
          defaultValue: 'http://10.0.2.2:8000',
        )).replaceAll(RegExp(r'/$'), '');

  final http.Client _client;
  final TokenStore _tokens;
  final String baseUrl;

  Future<UserProfile> login(String email, String password) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: const {'Content-Type': 'application/x-www-form-urlencoded'},
      body: {'username': email.trim(), 'password': password},
    );
    final payload = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(_message(payload, 'Login failed'), statusCode: response.statusCode);
    }
    await _tokens.write(payload['access_token'] as String);
    try {
      final profile = await currentUser();
      if (profile.role != 'POLICE') {
        throw const ApiException('This account is not authorized for the Police application.');
      }
      return profile;
    } catch (_) {
      await _tokens.clear();
      rethrow;
    }
  }

  Future<UserProfile> currentUser() async =>
      UserProfile.fromJson(await _authorizedJson('GET', '/auth/me'));

  Future<PatrolAssignment?> currentAssignment() async {
    try {
      return PatrolAssignment.fromJson(
        await _authorizedJson('GET', '/patrols/assignments/current'),
      );
    } on ApiException catch (error) {
      if (error.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<PatrolAssignment> transition(String assignmentId, String action) async =>
      PatrolAssignment.fromJson(
        await _authorizedJson('POST', '/patrols/assignments/$assignmentId/$action'),
      );

  Future<void> logout() => _tokens.clear();

  Future<Map<String, dynamic>> _authorizedJson(String method, String path) async {
    final token = await _tokens.read();
    if (token == null) throw const ApiException('Your session has expired.', statusCode: 401);
    final uri = Uri.parse('$baseUrl$path');
    final headers = {'Authorization': 'Bearer $token', 'Accept': 'application/json'};
    final response = method == 'POST'
        ? await _client.post(uri, headers: headers)
        : await _client.get(uri, headers: headers);
    final payload = _decode(response);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      if (response.statusCode == 401) await _tokens.clear();
      throw ApiException(_message(payload, 'SafeZone request failed'), statusCode: response.statusCode);
    }
    return payload;
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.body.isEmpty) return <String, dynamic>{};
    try {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } on FormatException {
      throw ApiException('The SafeZone API returned an unreadable response.', statusCode: response.statusCode);
    }
  }

  String _message(Map<String, dynamic> payload, String fallback) {
    final detail = payload['detail'];
    if (detail is String) return detail;
    if (detail is List) {
      return detail.map((item) => item is Map ? item['msg'] : item).join('; ');
    }
    return fallback;
  }
}
