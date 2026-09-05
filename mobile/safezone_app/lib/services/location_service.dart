import 'package:geolocator/geolocator.dart';
import 'package:safezone_app/models/patrol_assignment.dart';

class LocationUnavailableException implements Exception {
  const LocationUnavailableException(this.message);
  final String message;
  @override
  String toString() => message;
}

abstract interface class DeviceLocationService {
  Future<GeoPoint> determineCurrentPosition();
  double distanceMeters(GeoPoint from, GeoPoint to);
  Future<bool> openSettings();
}

class GeolocatorLocationService implements DeviceLocationService {
  static const recentLocationMaximumAge = Duration(minutes: 5);

  @override
  Future<bool> openSettings() => Geolocator.openAppSettings();

  @override
  Future<GeoPoint> determineCurrentPosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const LocationUnavailableException(
        'Location services are turned off. Enable device location and try again.',
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied) {
      throw const LocationUnavailableException(
        'Location permission was denied. SafeZone cannot calculate your distance to the PRP.',
      );
    }
    if (permission == LocationPermission.deniedForever) {
      throw const LocationUnavailableException(
        'Location permission is permanently denied. Enable it from device settings.',
      );
    }
    final cachedPosition = await _recentLastKnownPosition();
    if (cachedPosition != null) {
      return _pointFromPosition(cachedPosition);
    }
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      ).timeout(const Duration(seconds: 12));
      return _pointFromPosition(position);
    } on Exception {
      final recentPosition = await _recentLastKnownPosition();
      if (recentPosition != null) {
        return _pointFromPosition(recentPosition);
      }
      throw const LocationUnavailableException(
        'A current or recent location could not be obtained. Check GPS signal and try again.',
      );
    }
  }

  Future<Position?> _recentLastKnownPosition() async {
    try {
      final position = await Geolocator.getLastKnownPosition()
          .timeout(const Duration(seconds: 2));
      return position != null && isRecentLocationTimestamp(position.timestamp)
          ? position
          : null;
    } on Exception {
      return null;
    }
  }

  GeoPoint _pointFromPosition(Position position) => GeoPoint(
        latitude: position.latitude,
        longitude: position.longitude,
      );

  @override
  double distanceMeters(GeoPoint from, GeoPoint to) =>
      Geolocator.distanceBetween(
        from.latitude,
        from.longitude,
        to.latitude,
        to.longitude,
      );
}

bool isRecentLocationTimestamp(
  DateTime timestamp, {
  DateTime? now,
  Duration maximumAge = GeolocatorLocationService.recentLocationMaximumAge,
}) {
  final age = (now ?? DateTime.now()).toUtc().difference(timestamp.toUtc());
  return age >= const Duration(seconds: -30) && age <= maximumAge;
}
