import 'package:flutter/material.dart';
import 'dart:async';
import 'package:safezone_app/models/sos_request.dart';
import 'package:safezone_app/police/prp_assignment_screen.dart';
import 'package:safezone_app/police/sos_response_screen.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/services/location_service.dart';
import 'package:safezone_app/services/sos_event_channel.dart';
import 'package:safezone_app/services/session_controller.dart';
import 'package:safezone_app/shared/theme.dart';
import 'package:safezone_app/shared/widgets.dart';

class PoliceHomeScreen extends StatefulWidget {
  const PoliceHomeScreen({required this.session, super.key});
  final SessionController session;

  @override
  State<PoliceHomeScreen> createState() => _PoliceHomeScreenState();
}

class _PoliceHomeScreenState extends State<PoliceHomeScreen> {
  PoliceSOS? sos;
  String? sosError;
  Timer? locationTimer;
  StreamSubscription<Map<String, dynamic>>? events;
  late final SOSEventChannel eventChannel = SOSEventChannel(widget.session.api);
  final DeviceLocationService location = GeolocatorLocationService();

  @override
  void initState() {
    super.initState();
    refreshSOS();
    connectEvents();
    locationTimer =
        Timer.periodic(const Duration(seconds: 30), (_) => submitLocation());
  }

  Future<void> connectEvents() async {
    try {
      final stream = await eventChannel.connect();
      events = stream.listen((_) => refreshAll(), onError: (_) {});
    } on Exception {
      // Manual pull-to-refresh remains available while WebSocket is offline.
    }
  }

  Future<void> submitLocation() async {
    if (widget.session.assignment == null && sos == null) return;
    try {
      final point = await location.determineCurrentPosition();
      await widget.session.api
          .submitPoliceLocation(point.latitude, point.longitude);
    } on Exception {
      // Location readiness is shown in the response/assignment screens; never loop aggressively.
    }
  }

  @override
  void dispose() {
    locationTimer?.cancel();
    events?.cancel();
    eventChannel.close();
    super.dispose();
  }

  Future<void> refreshSOS() async {
    try {
      final value = await widget.session.api.currentPoliceSOS();
      if (mounted) {
        setState(() {
          sos = value;
          sosError = null;
        });
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => sosError = error.message);
    }
  }

  Future<void> refreshAll() async {
    await Future.wait([widget.session.refreshAssignment(), refreshSOS()]);
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final profile = session.profile!;
    final assignment = session.assignment;
    return Scaffold(
      appBar: AppBar(title: const SafeZoneLogo(compact: true), actions: [
        IconButton(
            tooltip: 'Sign out',
            onPressed: session.logout,
            icon: const Icon(Icons.logout))
      ]),
      body: RefreshIndicator(
        onRefresh: refreshAll,
        child: ListView(padding: const EdgeInsets.all(18), children: [
          Text('Welcome, ${profile.name.split(' ').first}',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800, color: SafeZoneTheme.navy)),
          const SizedBox(height: 4),
          Text(profile.email, style: const TextStyle(color: Color(0xFF667085))),
          const SizedBox(height: 20),
          if (session.errorMessage case final message?) ...[
            ErrorNotice(message),
            const SizedBox(height: 14)
          ],
          if (sosError case final message?) ...[
            ErrorNotice(message),
            const SizedBox(height: 14)
          ],
          if (sos case final incident?) ...[
            Card(
                color: const Color(0xFFFFE9E7),
                child: ListTile(
                  onTap: () async {
                    await Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (_) => SOSResponseScreen(
                                api: session.api, initial: incident)));
                    await refreshAll();
                  },
                  leading: const Icon(Icons.emergency,
                      color: SafeZoneTheme.danger, size: 36),
                  title: const Text('Emergency SOS assigned',
                      style: TextStyle(fontWeight: FontWeight.w900)),
                  subtitle: Text(
                      '${shortId(incident.id)} • ${incident.status.replaceAll('_', ' ')}'),
                  trailing: const Icon(Icons.chevron_right),
                )),
            const SizedBox(height: 14),
          ],
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Row(children: [
                    Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                            color: const Color(0xFFEAF7F0),
                            borderRadius: BorderRadius.circular(14)),
                        child: const Icon(Icons.local_police_outlined,
                            color: SafeZoneTheme.success)),
                    const SizedBox(width: 14),
                    Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                          const Text('Duty state',
                              style: TextStyle(
                                  color: Color(0xFF667085), fontSize: 12)),
                          const SizedBox(height: 3),
                          Text(
                              assignment == null
                                  ? 'No active assignment'
                                  : 'Assigned to patrol',
                              style: const TextStyle(
                                  fontWeight: FontWeight.w800, fontSize: 17)),
                          Text(
                              assignment == null
                                  ? 'Availability is managed by command'
                                  : assignment.status.replaceAll('_', ' '),
                              style: const TextStyle(
                                  color: Color(0xFF667085), fontSize: 12))
                        ]))
                  ]))),
          const SizedBox(height: 14),
          if (assignment == null)
            Card(
                child: Padding(
                    padding: const EdgeInsets.symmetric(
                        vertical: 42, horizontal: 22),
                    child: Column(children: [
                      const Icon(Icons.assignment_outlined,
                          size: 48, color: Color(0xFF98A2B3)),
                      const SizedBox(height: 14),
                      const Text('No current assignment',
                          style: TextStyle(
                              fontWeight: FontWeight.w800, fontSize: 18)),
                      const SizedBox(height: 6),
                      const Text(
                          'Pull down to refresh after command assigns an approved PRP.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Color(0xFF667085))),
                      const SizedBox(height: 18),
                      OutlinedButton.icon(
                          onPressed: session.refreshing
                              ? null
                              : session.refreshAssignment,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Check again'))
                    ])))
          else ...[
            Card(
                child: InkWell(
                    borderRadius: BorderRadius.circular(18),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => PrpAssignmentScreen(session: session))),
                    child: Padding(
                        padding: const EdgeInsets.all(19),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    const Text('CURRENT ASSIGNMENT',
                                        style: TextStyle(
                                            color: SafeZoneTheme.blue,
                                            fontWeight: FontWeight.w800,
                                            letterSpacing: 1,
                                            fontSize: 11)),
                                    _StatusBadge(assignment.status)
                                  ]),
                              const SizedBox(height: 18),
                              const Row(children: [
                                Icon(Icons.location_on,
                                    color: SafeZoneTheme.blue),
                                SizedBox(width: 9),
                                Text('Patrol Response Point',
                                    style: TextStyle(
                                        fontWeight: FontWeight.w800,
                                        fontSize: 18))
                              ]),
                              const SizedBox(height: 14),
                              _Detail(
                                  label: 'Shift',
                                  value:
                                      '${formatDateTime(assignment.shiftStart)} — ${formatDateTime(assignment.shiftEnd)}'),
                              _Detail(
                                  label: 'Patrol unit',
                                  value: shortId(assignment.patrolUnitId)),
                              const SizedBox(height: 12),
                              const Row(
                                  mainAxisAlignment: MainAxisAlignment.end,
                                  children: [
                                    Text('Open assignment',
                                        style: TextStyle(
                                            color: SafeZoneTheme.blue,
                                            fontWeight: FontWeight.w700)),
                                    SizedBox(width: 5),
                                    Icon(Icons.arrow_forward,
                                        size: 18, color: SafeZoneTheme.blue)
                                  ]),
                            ])))),
            const SizedBox(height: 14),
            OutlinedButton.icon(
                onPressed: null,
                icon: const Icon(Icons.person_off_outlined),
                label: const Text('Mark unavailable')),
            const Padding(
                padding: EdgeInsets.all(9),
                child: Text(
                    'Command must change availability. The current backend has no POLICE availability endpoint.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Color(0xFF667085), fontSize: 11))),
          ],
        ]),
      ),
    );
  }
}

class _Detail extends StatelessWidget {
  const _Detail({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
            width: 80,
            child:
                Text(label, style: const TextStyle(color: Color(0xFF667085)))),
        Expanded(
            child: Text(value,
                style: const TextStyle(fontWeight: FontWeight.w600)))
      ]));
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge(this.status);
  final String status;
  @override
  Widget build(BuildContext context) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
          color: const Color(0xFFEAF7F0),
          borderRadius: BorderRadius.circular(99)),
      child: Text(status.replaceAll('_', ' '),
          style: const TextStyle(
              color: SafeZoneTheme.success,
              fontWeight: FontWeight.w800,
              fontSize: 10)));
}
