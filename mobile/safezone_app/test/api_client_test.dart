import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:safezone_app/services/api_client.dart';

void main() {
  test('police login stores token and returns authorized profile', () async {
    final tokens = MemoryTokens();
    final client = ApiClient(
      baseUrl: 'http://safezone.test',
      tokenStore: tokens,
      client: MockClient((request) async {
        if (request.url.path == '/auth/login') {
          expect(request.bodyFields['username'], 'officer@example.com');
          return http.Response(
              jsonEncode({
                'access_token': 'opaque-token',
                'token_type': 'bearer',
                'expires_in': 1800
              }),
              200);
        }
        expect(request.headers['Authorization'], 'Bearer opaque-token');
        return http.Response(jsonEncode(policeProfile), 200);
      }),
    );

    final profile = await client.login('officer@example.com', 'valid-password');

    expect(profile.role, 'POLICE');
    expect(tokens.value, 'opaque-token');
  });

  test('non-police login is rejected and token is cleared', () async {
    final tokens = MemoryTokens();
    final client = ApiClient(
      baseUrl: 'http://safezone.test',
      tokenStore: tokens,
      client: MockClient((request) async {
        if (request.url.path == '/auth/login') {
          return http.Response(
              jsonEncode({'access_token': 'opaque-token'}), 200);
        }
        return http.Response(
            jsonEncode({...policeProfile, 'role': 'CITIZEN'}), 200);
      }),
    );

    await expectLater(client.login('citizen@example.com', 'password'),
        throwsA(isA<ApiException>()));
    expect(tokens.value, isNull);
  });

  test('missing current assignment is returned as null', () async {
    final tokens = MemoryTokens()..value = 'token';
    final client = ApiClient(
      baseUrl: 'http://safezone.test',
      tokenStore: tokens,
      client: MockClient((_) async =>
          http.Response(jsonEncode({'detail': 'Assignment not found'}), 404)),
    );

    expect(await client.currentAssignment(), isNull);
  });

  test('citizen login accepts only citizen profile', () async {
    final tokens = MemoryTokens();
    final client = ApiClient(
        baseUrl: 'http://safezone.test',
        tokenStore: tokens,
        client: MockClient((request) async {
          if (request.url.path == '/auth/login') {
            return http.Response(
                jsonEncode({'access_token': 'citizen-token'}), 200);
          }
          return http.Response(
              jsonEncode({...policeProfile, 'role': 'CITIZEN'}), 200);
        }));
    final profile = await client.loginForRole(
        'citizen@example.com', 'valid-password',
        expectedRole: 'CITIZEN');
    expect(profile.role, 'CITIZEN');
    expect(tokens.value, 'citizen-token');
  });

  test('emergency contacts remain owner-authorized API data', () async {
    final tokens = MemoryTokens()..value = 'citizen-token';
    final client = ApiClient(
        baseUrl: 'http://safezone.test',
        tokenStore: tokens,
        client: MockClient((request) async {
          expect(request.headers['Authorization'], 'Bearer citizen-token');
          return http.Response(
              jsonEncode([
                {
                  'id': 'contact-id',
                  'name': 'Mother',
                  'phone_number': '+91 9876543210',
                  'relationship_label': 'Parent'
                }
              ]),
              200);
        }));
    final contacts = await client.emergencyContacts();
    expect(contacts.single.name, 'Mother');
    expect(contacts.single.phoneNumber, '+91 9876543210');
  });

  test('citizen SOS sends location and parses privacy-scoped status', () async {
    final tokens = MemoryTokens()..value = 'citizen-token';
    final client = ApiClient(
        baseUrl: 'http://safezone.test',
        tokenStore: tokens,
        client: MockClient((request) async {
          expect(request.url.path, '/sos');
          expect(jsonDecode(request.body)['latitude'], 9.35);
          return http.Response(
              jsonEncode({
                'id': 'sos-1',
                'status': 'ASSIGNED',
                'created_at': '2026-09-05T08:00:00Z',
                'patrol_assigned': true,
                'approximate_responder_distance_meters': 800,
              }),
              201);
        }));
    final sos = await client.createSOS(9.35, 78.51);
    expect(sos.status, 'ASSIGNED');
    expect(sos.approximateResponderDistanceMeters, 800);
  });

  test('police SOS transition uses the requested lifecycle action', () async {
    final tokens = MemoryTokens()..value = 'police-token';
    final client = ApiClient(
        baseUrl: 'http://safezone.test',
        tokenStore: tokens,
        client: MockClient((request) async {
          expect(request.url.path, '/sos/sos-2/accept');
          return http.Response(
              jsonEncode({
                'id': 'sos-2',
                'status': 'ACCEPTED',
                'created_at': '2026-09-05T08:00:00Z',
                'emergency_location': {'latitude': 9.35, 'longitude': 78.51},
              }),
              200);
        }));
    expect((await client.transitionSOS('sos-2', 'accept')).status, 'ACCEPTED');
  });

  test('live location uses scoped REST endpoint and websocket URL is derived',
      () async {
    final tokens = MemoryTokens()..value = 'police-token';
    final client = ApiClient(
      baseUrl: 'https://safezone.test/api-root',
      tokenStore: tokens,
      client: MockClient((request) async {
        expect(request.url.path, '/api-root/live/police/location');
        expect(request.headers['Authorization'], 'Bearer police-token');
        return http.Response('{}', 200);
      }),
    );
    await client.submitPoliceLocation(9.35, 78.51);
    expect(client.sosWebSocketUrl, 'wss://safezone.test/api-root/ws/sos');
  });
}

const policeProfile = {
  'id': '00000000-0000-0000-0000-000000000001',
  'name': 'Officer Test',
  'email': 'officer@example.com',
  'role': 'POLICE',
  'is_active': true,
  'created_at': '2026-09-04T08:00:00Z',
  'updated_at': '2026-09-04T08:00:00Z',
};

class MemoryTokens implements TokenStore {
  String? value;
  @override
  Future<void> clear() async => value = null;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String token) async => value = token;
}
