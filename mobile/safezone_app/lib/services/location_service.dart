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
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 15),
        ),
      );
      return GeoPoint(
          latitude: position.latitude, longitude: position.longitude);
    } on Exception {
      throw const LocationUnavailableException(
        'Your current location could not be obtained. Check GPS signal and try again.',
      );
    }
  }

  @override
  double distanceMeters(GeoPoint from, GeoPoint to) =>
      Geolocator.distanceBetween(
        from.latitude,
        from.longitude,
        to.latitude,
        to.longitude,
      );
}
