import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:safezone_app/models/patrol_assignment.dart';
import 'package:safezone_app/services/location_service.dart';
import 'package:safezone_app/services/session_controller.dart';
import 'package:safezone_app/shared/theme.dart';
import 'package:safezone_app/shared/widgets.dart';
import 'package:url_launcher/url_launcher.dart';

class PrpAssignmentScreen extends StatefulWidget {
  const PrpAssignmentScreen({required this.session, super.key, this.locationService});
  final SessionController session;
  final DeviceLocationService? locationService;
  @override
  State<PrpAssignmentScreen> createState() => _PrpAssignmentScreenState();
}

class _PrpAssignmentScreenState extends State<PrpAssignmentScreen> {
  late final DeviceLocationService locations = widget.locationService ?? GeolocatorLocationService();
  GeoPoint? currentLocation;
  String? locationError;
  bool locating = false;

  @override
  void initState() { super.initState(); locate(); }

  Future<void> locate() async {
    setState(() { locating = true; locationError = null; });
    try { final point = await locations.determineCurrentPosition(); if (mounted) setState(() => currentLocation = point); }
    on LocationUnavailableException catch (error) { if (mounted) setState(() => locationError = error.message); }
    finally { if (mounted) setState(() => locating = false); }
  }

  Future<void> transition(String action, String successMessage) async {
    final success = await widget.session.transition(action);
    if (!mounted) return;
    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(successMessage)));
      if (action == 'complete') { await widget.session.refreshAssignment(silent: true); if (mounted) Navigator.of(context).pop(); }
      else { setState(() {}); }
    }
  }

  Future<void> openNavigation(GeoPoint target) async {
    final coordinates = '${target.latitude},${target.longitude}';
    final uri = Uri(scheme: 'geo', path: coordinates, queryParameters: {'q': '$coordinates(SafeZone PRP)'});
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No navigation application is available on this device.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final assignment = widget.session.assignment;
    if (assignment == null) return const Scaffold(body: Center(child: Text('This assignment is no longer active.')));
    final target = assignment.prpLocation;
    final distance = currentLocation == null ? null : locations.distanceMeters(currentLocation!, target);
    final markers = [
      Marker(point: LatLng(target.latitude, target.longitude), width: 48, height: 48, child: const Icon(Icons.location_pin, size: 46, color: Color(0xFFB42318))),
      if (currentLocation case final point?) Marker(point: LatLng(point.latitude, point.longitude), width: 34, height: 34, child: Container(decoration: BoxDecoration(color: SafeZoneTheme.blue, shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3), boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 5)]))),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('PRP assignment'), actions: [IconButton(tooltip: 'Refresh location', onPressed: locating ? null : locate, icon: const Icon(Icons.my_location))]),
      body: ListView(children: [
        SizedBox(height: 300, child: FlutterMap(options: MapOptions(initialCenter: LatLng(target.latitude, target.longitude), initialZoom: 15), children: [
          TileLayer(urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', userAgentPackageName: 'com.safezone.safezone_app'),
          if (currentLocation case final point?) PolylineLayer(polylines: [Polyline(points: [LatLng(point.latitude, point.longitude), LatLng(target.latitude, target.longitude)], color: SafeZoneTheme.blue.withValues(alpha: .65), strokeWidth: 4, pattern: const StrokePattern.dotted())]),
          MarkerLayer(markers: markers),
          const RichAttributionWidget(attributions: [TextSourceAttribution('OpenStreetMap contributors')]),
        ])),
        Padding(padding: const EdgeInsets.all(18), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Expanded(child: Text('Assigned patrol point', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))), _Badge(assignment.status)]),
          const SizedBox(height: 8),
          Text('${target.latitude.toStringAsFixed(6)}, ${target.longitude.toStringAsFixed(6)}', style: const TextStyle(color: Color(0xFF667085))),
          const SizedBox(height: 18),
          Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
            _Info(icon: Icons.schedule, label: 'Current shift', value: '${formatDateTime(assignment.shiftStart)}\n${formatDateTime(assignment.shiftEnd)}'),
            const Divider(height: 25),
            _Info(icon: Icons.route_outlined, label: 'Straight-line proximity', value: locating ? 'Locating…' : distance == null ? 'Location unavailable' : distance >= 1000 ? '${(distance / 1000).toStringAsFixed(1)} km' : '${distance.round()} m'),
            const Divider(height: 25),
            const _Info(icon: Icons.directions_car_outlined, label: 'Road route / ETA', value: 'Unavailable from the current mobile API'),
          ]))),
          if (locationError case final message?) ...[const SizedBox(height: 13), ErrorNotice(message), TextButton.icon(onPressed: locations.openSettings, icon: const Icon(Icons.settings_outlined), label: const Text('Open location settings'))],
          if (widget.session.errorMessage case final message?) ...[const SizedBox(height: 13), ErrorNotice(message)],
          const SizedBox(height: 16),
          OutlinedButton.icon(onPressed: () => openNavigation(target), icon: const Icon(Icons.navigation_outlined), label: const Text('Open in navigation app')),
          const SizedBox(height: 10),
          if (assignment.canAcknowledge) FilledButton.icon(onPressed: widget.session.refreshing ? null : () => transition('acknowledge', 'Assignment acknowledged.'), icon: const Icon(Icons.check_circle_outline), label: const Text('Acknowledge assignment')),
          if (assignment.canArrive) FilledButton.icon(onPressed: widget.session.refreshing ? null : () => transition('arrive', 'Arrival at PRP recorded.'), icon: const Icon(Icons.location_on_outlined), label: const Text('Mark arrived at PRP')),
          if (assignment.canComplete) ...[const SizedBox(height: 10), OutlinedButton.icon(onPressed: widget.session.refreshing ? null : () => transition('complete', 'Assignment completed.'), icon: const Icon(Icons.flag_outlined), label: const Text('Complete assignment'))],
          const SizedBox(height: 14),
          Text('Assignment ${shortId(assignment.id)} · Patrol ${shortId(assignment.patrolUnitId)}', textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF98A2B3), fontSize: 11)),
        ])),
      ]),
    );
  }
}

class _Info extends StatelessWidget { const _Info({required this.icon, required this.label, required this.value}); final IconData icon; final String label; final String value; @override Widget build(BuildContext context) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(icon, color: SafeZoneTheme.blue), const SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: const TextStyle(color: Color(0xFF667085), fontSize: 12)), const SizedBox(height: 3), Text(value, style: const TextStyle(fontWeight: FontWeight.w700, height: 1.4))]))]); }
class _Badge extends StatelessWidget { const _Badge(this.status); final String status; @override Widget build(BuildContext context) => Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6), decoration: BoxDecoration(color: const Color(0xFFEAF7F0), borderRadius: BorderRadius.circular(99)), child: Text(status.replaceAll('_', ' '), style: const TextStyle(color: SafeZoneTheme.success, fontWeight: FontWeight.w800, fontSize: 10))); }
