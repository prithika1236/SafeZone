import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:safezone_app/main.dart';
import 'package:safezone_app/models/patrol_assignment.dart';
import 'package:safezone_app/models/user_profile.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/services/session_controller.dart';

void main() {
  testWidgets('renders citizen authentication after session restoration',
      (tester) async {
    final session = SessionController(apiClient: _SignedOutApi());
    await tester.pumpWidget(SafeZoneApp(sessionController: session));
    await tester.pumpAndSettle();

    expect(find.text('Citizen sign in'), findsOneWidget);
    expect(find.text('Police officer sign in'), findsOneWidget);
  });

  testWidgets('routes an authenticated citizen to citizen home',
      (tester) async {
    final session = SessionController(apiClient: _CitizenApi());
    await tester.pumpWidget(SafeZoneApp(sessionController: session));
    await tester.pumpAndSettle();

    expect(find.text('SafeZone Citizen'), findsOneWidget);
    expect(
        find.text('SOS dispatch is not active in this stage.'), findsOneWidget);
    expect(find.text('Emergency support when you need it.'), findsOneWidget);
  });

  testWidgets('routes an authenticated police user to police home',
      (tester) async {
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

class _CitizenApi extends _SignedOutApi {
  @override
  Future<UserProfile> currentUser() async => const UserProfile(
        id: 'citizen-id',
        name: 'Citizen Test',
        email: 'citizen@example.com',
        role: 'CITIZEN',
        isActive: true,
      );
}
