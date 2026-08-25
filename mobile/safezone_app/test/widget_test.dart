import 'package:flutter_test/flutter_test.dart';
import 'package:safezone_app/main.dart';

void main() {
  testWidgets('renders the foundation shell', (WidgetTester tester) async {
    await tester.pumpWidget(const SafeZoneApp());

    expect(find.text('SafeZone foundation is ready'), findsOneWidget);
  });
}
