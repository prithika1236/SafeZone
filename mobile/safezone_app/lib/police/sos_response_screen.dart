import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:safezone_app/models/sos_request.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/shared/theme.dart';
import 'package:safezone_app/shared/widgets.dart';
import 'package:url_launcher/url_launcher.dart';

class SOSResponseScreen extends StatefulWidget {
  const SOSResponseScreen(
      {super.key, required this.api, required this.initial});
  final ApiClient api;
  final PoliceSOS initial;

  @override
  State<SOSResponseScreen> createState() => _SOSResponseScreenState();
}

class _SOSResponseScreenState extends State<SOSResponseScreen> {
  late PoliceSOS sos = widget.initial;
  bool working = false;
  String? error;

  Future<void> advance() async {
    final action = sos.nextAction;
    if (action == null) return;
    setState(() {
      working = true;
      error = null;
    });
    try {
      final value = await widget.api.transitionSOS(sos.id, action);
      if (mounted) setState(() => sos = value);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> navigate() async {
    final uri = Uri.parse(
        'geo:${sos.latitude},${sos.longitude}?q=${sos.latitude},${sos.longitude}(SOS)');
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) &&
        mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('No navigation application is available.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final accepted = sos.status != 'ASSIGNED';
    final destination = LatLng(sos.latitude, sos.longitude);
    return Scaffold(
      appBar: AppBar(title: const Text('SOS response')),
      body: ListView(padding: const EdgeInsets.all(18), children: [
        const Icon(Icons.emergency, size: 58, color: SafeZoneTheme.danger),
        Text('Emergency ${shortId(sos.id)}',
            textAlign: TextAlign.center,
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(fontWeight: FontWeight.w900)),
        Text(formatDateTime(sos.createdAt), textAlign: TextAlign.center),
        const SizedBox(height: 18),
        if (error != null) ErrorNotice(error!),
        Card(
            child: ListTile(
          leading: const Icon(Icons.route, color: SafeZoneTheme.blue),
          title: Text(sos.responderDistanceMeters == null
              ? 'Distance unavailable'
              : '${(sos.responderDistanceMeters! / 1000).toStringAsFixed(1)} km away'),
          subtitle: Text(sos.estimatedDurationSeconds == null
              ? 'Straight-line proximity used; route ETA unavailable'
              : 'Estimated ${(sos.estimatedDurationSeconds! / 60).ceil()} minutes by route'),
          trailing: Text(sos.status.replaceAll('_', ' '),
              style: const TextStyle(fontWeight: FontWeight.w800)),
        )),
        const SizedBox(height: 14),
        if (!accepted)
          const Card(
              child: Padding(
                  padding: EdgeInsets.all(18),
                  child: Text(
                      'Accept the incident to reveal navigation details required for response.')))
        else ...[
          SizedBox(
              height: 300,
              child: ClipRRect(
                  borderRadius: BorderRadius.circular(18),
                  child: FlutterMap(
                    options:
                        MapOptions(initialCenter: destination, initialZoom: 16),
                    children: [
                      TileLayer(
                          urlTemplate:
                              'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                          userAgentPackageName: 'com.safezone.safezone_app'),
                      MarkerLayer(markers: [
                        Marker(
                            point: destination,
                            width: 54,
                            height: 54,
                            child: const Icon(Icons.location_on,
                                color: SafeZoneTheme.danger, size: 48))
                      ]),
                    ],
                  ))),
          const SizedBox(height: 12),
          OutlinedButton.icon(
              onPressed: navigate,
              icon: const Icon(Icons.navigation),
              label: const Text('Open navigation')),
        ],
        const SizedBox(height: 18),
        if (sos.nextAction != null)
          FilledButton.icon(
              onPressed: working ? null : advance,
              icon: const Icon(Icons.local_police),
              label: Text(working
                  ? 'Updating...'
                  : switch (sos.nextAction) {
                      'accept' => 'Accept SOS',
                      'en-route' => 'Begin response',
                      'arrive' => 'Mark arrived',
                      'resolve' => 'Resolve incident',
                      _ => 'Update'
                    })),
      ]),
    );
  }
}
