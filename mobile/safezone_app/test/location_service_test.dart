import 'package:flutter_test/flutter_test.dart';
import 'package:safezone_app/services/location_service.dart';

void main() {
  final now = DateTime.utc(2026, 9, 5, 13);

  test('accepts a recent fallback location', () {
    expect(
      isRecentLocationTimestamp(
        now.subtract(const Duration(minutes: 2)),
        now: now,
      ),
      isTrue,
    );
  });

  test('rejects a stale fallback location', () {
    expect(
      isRecentLocationTimestamp(
        now.subtract(const Duration(minutes: 6)),
        now: now,
      ),
      isFalse,
    );
  });

  test('rejects an implausibly future fallback location', () {
    expect(
      isRecentLocationTimestamp(
        now.add(const Duration(minutes: 1)),
        now: now,
      ),
      isFalse,
    );
  });
}
