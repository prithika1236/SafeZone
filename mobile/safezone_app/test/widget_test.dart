import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:safezone_app/main.dart';
import 'package:safezone_app/models/patrol_assignment.dart';
import 'package:safezone_app/models/user_profile.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/services/session_controller.dart';

void main() {
  testWidgets('renders the police login after session restoration', (tester) async {
    final session = SessionController(apiClient: _SignedOutApi());
    await tester.pumpWidget(SafeZoneApp(sessionController: session));
    await tester.pumpAndSettle();

    expect(find.text('Ready for duty?'), findsOneWidget);
    expect(find.text('Sign in securely'), findsOneWidget);
    expect(find.text('Authorized POLICE accounts only'), findsOneWidget);
  });

  testWidgets('routes an authenticated police user to police home', (tester) async {
    final session = SessionController(apiClient: _PoliceApi());
    await tester.pumpWidget(SafeZoneApp(sessionController: session));
    await tester.pumpAndSettle();

    expect(find.text('Welcome, Officer'), findsOneWidget);
    expect(find.text('No current assignment'), findsOneWidget);
  });
}

class _MemoryTokens implements TokenStore {
  @override
  Future<void> clear() async {}
  @override
  Future<String?> read() async => null;
  @override
  Future<void> write(String token) async {}
}

class _SignedOutApi extends ApiClient {
  _SignedOutApi()
      : super(
          client: MockClient((_) async => http.Response('{}', 401)),
          tokenStore: _MemoryTokens(),
          baseUrl: 'http://test',
        );

  @override
  Future<void> logout() async {}
}

class _PoliceApi extends _SignedOutApi {
  @override
  Future<UserProfile> currentUser() async => const UserProfile(
        id: 'user-id',
        name: 'Officer Test',
        email: 'officer@example.com',
        role: 'POLICE',
        isActive: true,
      );

  @override
  Future<PatrolAssignment?> currentAssignment() async => null;
}
