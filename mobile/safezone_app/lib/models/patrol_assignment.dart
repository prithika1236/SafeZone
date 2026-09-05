class GeoPoint {
  const GeoPoint({required this.latitude, required this.longitude});

  factory GeoPoint.fromJson(Map<String, dynamic> json) => GeoPoint(
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
      );

  final double latitude;
  final double longitude;
}

class PatrolAssignment {
  const PatrolAssignment({
    required this.id,
    required this.patrolUnitId,
    required this.officerId,
    required this.prpId,
    required this.prpLocation,
    required this.shiftStart,
    required this.shiftEnd,
    required this.status,
    this.straightLineDistanceMeters,
  });

  factory PatrolAssignment.fromJson(Map<String, dynamic> json) =>
      PatrolAssignment(
        id: json['id'] as String,
        patrolUnitId: json['patrol_unit_id'] as String,
        officerId: json['police_officer_id'] as String,
        prpId: json['prp_location_id'] as String,
        prpLocation:
            GeoPoint.fromJson(json['prp_location'] as Map<String, dynamic>),
        shiftStart: DateTime.parse(json['shift_start'] as String),
        shiftEnd: DateTime.parse(json['shift_end'] as String),
        status: json['status'] as String,
        straightLineDistanceMeters:
            (json['straight_line_distance_meters'] as num?)?.toDouble(),
      );

  final String id;
  final String patrolUnitId;
  final String officerId;
  final String prpId;
  final GeoPoint prpLocation;
  final DateTime shiftStart;
  final DateTime shiftEnd;
  final String status;
  final double? straightLineDistanceMeters;

  bool get canAcknowledge => status == 'ASSIGNED';
  bool get canArrive => status == 'ACKNOWLEDGED';
  bool get canComplete => status == 'ACKNOWLEDGED' || status == 'AT_PRP';
}
