import 'package:flutter_test/flutter_test.dart';
import 'package:safezone_app/models/sos_request.dart';

void main() {
  test('citizen SOS exposes lifecycle behavior without operational location',
      () {
    final sos = CitizenSOS.fromJson({
      'id': 'request-1',
      'status': 'ASSIGNED',
      'created_at': '2026-09-05T08:00:00Z',
      'patrol_assigned': true,
      'approximate_responder_distance_meters': 1200,
    });
    expect(sos.canCancel, isTrue);
    expect(sos.approximateResponderDistanceMeters, 1200);
  });

  test('police SOS maps lifecycle to deterministic next action', () {
    final sos = PoliceSOS.fromJson({
      'id': 'request-2',
      'status': 'ACCEPTED',
      'created_at': '2026-09-05T08:00:00Z',
      'emergency_location': {'latitude': 9.35, 'longitude': 78.51},
    });
    expect(sos.nextAction, 'en-route');
    expect(sos.latitude, 9.35);
  });
}
