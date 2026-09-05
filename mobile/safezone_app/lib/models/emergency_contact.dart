class EmergencyContact {
  const EmergencyContact({
    required this.id,
    required this.name,
    required this.phoneNumber,
    this.relationshipLabel,
  });

  factory EmergencyContact.fromJson(Map<String, dynamic> json) =>
      EmergencyContact(
        id: json['id'] as String,
        name: json['name'] as String,
        phoneNumber: json['phone_number'] as String,
        relationshipLabel: json['relationship_label'] as String?,
      );

  final String id;
  final String name;
  final String phoneNumber;
  final String? relationshipLabel;
}
