import 'package:flutter/material.dart';
import 'package:safezone_app/citizen/emergency_contacts_screen.dart';
import 'package:safezone_app/citizen/sos_status_screen.dart';
import 'package:safezone_app/models/patrol_assignment.dart';
import 'package:safezone_app/models/sos_request.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/services/location_service.dart';
import 'package:safezone_app/services/session_controller.dart';
import 'package:safezone_app/shared/theme.dart';

class CitizenHomeScreen extends StatefulWidget {
  const CitizenHomeScreen(
      {super.key, required this.session, this.locationService});
  final SessionController session;
  final DeviceLocationService? locationService;
  @override
  State<CitizenHomeScreen> createState() => _CitizenHomeScreenState();
}

class _CitizenHomeScreenState extends State<CitizenHomeScreen> {
  late final DeviceLocationService location =
      widget.locationService ?? GeolocatorLocationService();
  GeoPoint? currentPosition;
  String locationMessage = 'Location has not been checked.';
  bool checkingLocation = false;
  bool submittingSOS = false;
  CitizenSOS? activeSOS;

  @override
  void initState() {
    super.initState();
    loadSOS();
  }

  Future<void> loadSOS() async {
    try {
      final value = await widget.session.api.currentCitizenSOS();
      if (mounted) {
        setState(() => activeSOS = value?.isTerminal == true ? null : value);
      }
    } on ApiException {
      // The status screen provides detailed errors after a request exists.
    }
  }

  Future<void> checkLocation() async {
    setState(() {
      checkingLocation = true;
      locationMessage = 'Checking device location…';
    });
    try {
      final value = await location.determineCurrentPosition();
      if (mounted) {
        setState(() {
          currentPosition = value;
          locationMessage = 'Location is available for emergency use.';
        });
      }
    } on LocationUnavailableException catch (error) {
      if (mounted) {
        setState(() {
          currentPosition = null;
          locationMessage = error.message;
        });
      }
    } finally {
      if (mounted) setState(() => checkingLocation = false);
    }
  }

  Future<void> submitSOS() async {
    if (activeSOS case final existing?) {
      await openStatus(existing);
      return;
    }
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              icon: const Icon(Icons.warning_amber_rounded,
                  color: SafeZoneTheme.danger, size: 42),
              title: const Text('Send emergency SOS?'),
              content: const Text(
                  'SafeZone will send your current location to police dispatch.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Send SOS'))
              ],
            ));
    if (confirmed != true) return;
    setState(() => submittingSOS = true);
    try {
      var point = currentPosition;
      point ??= await location.determineCurrentPosition();
      final sos =
          await widget.session.api.createSOS(point.latitude, point.longitude);
      if (!mounted) return;
      setState(() {
        currentPosition = point;
        activeSOS = sos;
      });
      await openStatus(sos);
    } on LocationUnavailableException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => submittingSOS = false);
    }
  }

  Future<void> openStatus(CitizenSOS sos) async {
    await Navigator.push(
        context,
        MaterialPageRoute(
            builder: (_) =>
                CitizenSOSStatusScreen(api: widget.session.api, initial: sos)));
    await loadSOS();
  }

  @override
  Widget build(BuildContext context) {
    final profile = widget.session.profile!;
    return Scaffold(
      appBar: AppBar(title: const Text('SafeZone Citizen'), actions: [
        IconButton(
            tooltip: 'Sign out',
            onPressed: widget.session.logout,
            icon: const Icon(Icons.logout)),
      ]),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        Text('Hello, ${profile.name.split(' ').first}',
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 6),
        const Text('Emergency support when you need it.'),
        const SizedBox(height: 24),
        Center(
            child: Semantics(
                button: true,
                label: 'SOS emergency button',
                child: InkWell(
                  onTap: submittingSOS ? null : submitSOS,
                  borderRadius: BorderRadius.circular(90),
                  child: Container(
                      width: 174,
                      height: 174,
                      decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: SafeZoneTheme.danger,
                          boxShadow: [
                            BoxShadow(
                                color:
                                    SafeZoneTheme.danger.withValues(alpha: .28),
                                blurRadius: 24,
                                spreadRadius: 7)
                          ]),
                      alignment: Alignment.center,
                      child: const Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.sos_rounded,
                                size: 62, color: Colors.white),
                            Text('EMERGENCY',
                                style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w800)),
                          ])),
                ))),
        const SizedBox(height: 16),
        Text(
            activeSOS == null
                ? 'Tap only when you need immediate assistance.'
                : 'Active emergency: ${activeSOS!.status.replaceAll('_', ' ')}',
            textAlign: TextAlign.center),
        const SizedBox(height: 28),
        Card(
            child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(children: [
                        Icon(Icons.my_location, color: SafeZoneTheme.blue),
                        SizedBox(width: 10),
                        Text('Location readiness',
                            style: TextStyle(fontWeight: FontWeight.w800))
                      ]),
                      const SizedBox(height: 12),
                      Text(locationMessage),
                      const SizedBox(height: 14),
                      OutlinedButton.icon(
                          onPressed: checkingLocation ? null : checkLocation,
                          icon: const Icon(Icons.location_searching),
                          label: Text(checkingLocation
                              ? 'Checking…'
                              : 'Check location')),
                      if (currentPosition == null &&
                          locationMessage.contains('settings'))
                        TextButton(
                            onPressed: location.openSettings,
                            child: const Text('Open device settings')),
                    ]))),
        const SizedBox(height: 14),
        Card(
            child: ListTile(
          leading: const Icon(Icons.health_and_safety_outlined,
              color: SafeZoneTheme.success),
          onTap: activeSOS == null ? null : () => openStatus(activeSOS!),
          title: const Text('Emergency status'),
          subtitle: Text(activeSOS == null
              ? 'No active emergency'
              : activeSOS!.status.replaceAll('_', ' ')),
          trailing: activeSOS == null ? null : const Icon(Icons.chevron_right),
        )),
        const SizedBox(height: 14),
        Card(
            child: ListTile(
          onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) =>
                      EmergencyContactsScreen(api: widget.session.api))),
          leading:
              const Icon(Icons.contacts_outlined, color: SafeZoneTheme.blue),
          title: const Text('Emergency contacts'),
          subtitle: const Text('Add and manage trusted contacts'),
          trailing: const Icon(Icons.chevron_right),
        )),
        const SizedBox(height: 16),
        const Text(
            'For your safety, operational patrol positions are never shown in the Citizen application.',
            style: TextStyle(color: Colors.black54),
            textAlign: TextAlign.center),
      ]),
    );
  }
}
