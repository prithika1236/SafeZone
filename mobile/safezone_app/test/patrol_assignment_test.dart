import 'package:flutter_test/flutter_test.dart';
import 'package:safezone_app/models/patrol_assignment.dart';

void main() {
  test('assignment lifecycle exposes only valid police actions', () {
    final assigned = PatrolAssignment.fromJson({...payload, 'status': 'ASSIGNED'});
    final acknowledged = PatrolAssignment.fromJson({...payload, 'status': 'ACKNOWLEDGED'});
    final arrived = PatrolAssignment.fromJson({...payload, 'status': 'AT_PRP'});

    expect(assigned.canAcknowledge, isTrue);
    expect(assigned.canArrive, isFalse);
    expect(acknowledged.canArrive, isTrue);
    expect(acknowledged.canComplete, isTrue);
    expect(arrived.canComplete, isTrue);
  });
}

const payload = {
  'id': '00000000-0000-0000-0000-000000000001',
  'patrol_unit_id': '00000000-0000-0000-0000-000000000002',
  'police_officer_id': '00000000-0000-0000-0000-000000000003',
  'prp_location_id': '00000000-0000-0000-0000-000000000004',
  'prp_location': {'latitude': 12.9716, 'longitude': 77.5946},
  'shift_start': '2026-09-04T08:00:00Z',
  'shift_end': '2026-09-04T16:00:00Z',
  'assigned_at': '2026-09-04T07:45:00Z',
  'updated_at': '2026-09-04T07:45:00Z',
};
