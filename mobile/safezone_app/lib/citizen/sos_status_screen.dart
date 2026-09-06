import 'dart:async';

import 'package:flutter/material.dart';
import 'package:safezone_app/models/sos_request.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/services/sos_event_channel.dart';
import 'package:safezone_app/shared/theme.dart';
import 'package:safezone_app/shared/widgets.dart';

class CitizenSOSStatusScreen extends StatefulWidget {
  const CitizenSOSStatusScreen(
      {super.key, required this.api, required this.initial});
  final ApiClient api;
  final CitizenSOS initial;
  @override
  State<CitizenSOSStatusScreen> createState() => _CitizenSOSStatusScreenState();
}

class _CitizenSOSStatusScreenState extends State<CitizenSOSStatusScreen> {
  late CitizenSOS sos = widget.initial;
  StreamSubscription<Map<String, dynamic>>? events;
  late final SOSEventChannel eventChannel = SOSEventChannel(widget.api);
  String? error;
  bool working = false;

  static const stages = [
    'PENDING',
    'ASSIGNED',
    'ACCEPTED',
    'EN_ROUTE',
    'ARRIVED',
    'RESOLVED'
  ];

  @override
  void initState() {
    super.initState();
    if (!sos.isTerminal) connectEvents();
  }

  Future<void> connectEvents() async {
    try {
      final stream = await eventChannel.connect();
      events = stream.listen((event) {
        if (event['sos_id'] == sos.id) refresh();
      }, onError: (_) {});
    } on Exception {
      // Pull-to-refresh remains available when local WebSocket service is offline.
    }
  }

  @override
  void dispose() {
    events?.cancel();
    eventChannel.close();
    super.dispose();
  }

  Future<void> refresh() async {
    try {
      final current = await widget.api.currentCitizenSOS();
      if (current != null && mounted) {
        setState(() {
          sos = current;
          error = null;
        });
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  Future<void> cancel() async {
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              title: const Text('Cancel SOS?'),
              content: const Text(
                  'Cancellation is allowed only before the officer accepts the emergency.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Keep active')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Cancel SOS'))
              ],
            ));
    if (confirmed != true) return;
    setState(() => working = true);
    try {
      sos = await widget.api.cancelSOS(sos.id);
      await events?.cancel();
      eventChannel.close();
    } on ApiException catch (exception) {
      error = exception.message;
    }
    if (mounted) setState(() => working = false);
  }

  @override
  Widget build(BuildContext context) {
    final currentIndex = stages.indexOf(sos.status);
    return Scaffold(
      appBar: AppBar(title: const Text('Emergency status')),
      body: RefreshIndicator(
          onRefresh: refresh,
          child: ListView(padding: const EdgeInsets.all(20), children: [
            Icon(
                sos.status == 'RESOLVED' ? Icons.check_circle : Icons.emergency,
                size: 64,
                color: sos.status == 'RESOLVED'
                    ? SafeZoneTheme.success
                    : SafeZoneTheme.danger),
            const SizedBox(height: 12),
            Text(sos.status.replaceAll('_', ' '),
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w900)),
            Text(
                'Request ${shortId(sos.id)} • ${formatDateTime(sos.createdAt)}',
                textAlign: TextAlign.center),
            if (error != null) ...[
              const SizedBox(height: 14),
              ErrorNotice(error!)
            ],
            const SizedBox(height: 24),
            ...stages.asMap().entries.map((entry) {
              final reached = currentIndex >= entry.key;
              return ListTile(
                leading: Icon(
                    reached ? Icons.check_circle : Icons.radio_button_unchecked,
                    color: reached ? SafeZoneTheme.success : Colors.grey),
                title: Text(entry.value.replaceAll('_', ' ')),
              );
            }),
            if (sos.approximateResponderDistanceMeters case final distance?)
              Card(
                  child: ListTile(
                      leading: const Icon(Icons.route),
                      title: const Text('Approximate responder distance'),
                      subtitle: Text(
                          'About ${(distance / 1000).toStringAsFixed(1)} km'))),
            if (!sos.patrolAssigned && sos.status == 'PENDING')
              const Card(
                  child: Padding(
                      padding: EdgeInsets.all(18),
                      child: Text(
                          'Your SOS is recorded. No suitable patrol is currently available; dispatch remains pending.'))),
            if (sos.canCancel) ...[
              const SizedBox(height: 18),
              OutlinedButton(
                  onPressed: working ? null : cancel,
                  child: const Text('Cancel SOS'))
            ],
          ])),
    );
  }
}
