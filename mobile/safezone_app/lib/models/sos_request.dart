class CitizenSOS {
  const CitizenSOS({
    required this.id,
    required this.status,
    required this.createdAt,
    required this.patrolAssigned,
    this.approximateResponderDistanceMeters,
    this.estimatedDurationSeconds,
  });

  factory CitizenSOS.fromJson(Map<String, dynamic> json) => CitizenSOS(
        id: json['id'] as String,
        status: json['status'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        patrolAssigned: json['patrol_assigned'] as bool,
        approximateResponderDistanceMeters:
            (json['approximate_responder_distance_meters'] as num?)?.toInt(),
        estimatedDurationSeconds:
            (json['estimated_duration_seconds'] as num?)?.toInt(),
      );

  final String id;
  final String status;
  final DateTime createdAt;
  final bool patrolAssigned;
  final int? approximateResponderDistanceMeters;
  final int? estimatedDurationSeconds;

  bool get canCancel => status == 'PENDING' || status == 'ASSIGNED';
  bool get isTerminal => status == 'RESOLVED' || status == 'CANCELLED';
}

class PoliceSOS {
  const PoliceSOS({
    required this.id,
    required this.status,
    required this.createdAt,
    required this.latitude,
    required this.longitude,
    this.responderDistanceMeters,
    this.estimatedDurationSeconds,
    this.distanceSource,
  });

  factory PoliceSOS.fromJson(Map<String, dynamic> json) {
    final location = json['emergency_location'] as Map<String, dynamic>;
    return PoliceSOS(
      id: json['id'] as String,
      status: json['status'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      latitude: (location['latitude'] as num).toDouble(),
      longitude: (location['longitude'] as num).toDouble(),
      responderDistanceMeters:
          (json['responder_distance_meters'] as num?)?.toDouble(),
      estimatedDurationSeconds:
          (json['estimated_duration_seconds'] as num?)?.toDouble(),
      distanceSource: json['distance_source'] as String?,
    );
  }

  final String id;
  final String status;
  final DateTime createdAt;
  final double latitude;
  final double longitude;
  final double? responderDistanceMeters;
  final double? estimatedDurationSeconds;
  final String? distanceSource;

  String? get nextAction => switch (status) {
        'ASSIGNED' => 'accept',
        'ACCEPTED' => 'en-route',
        'EN_ROUTE' => 'arrive',
        'ARRIVED' => 'resolve',
        _ => null,
      };
}
