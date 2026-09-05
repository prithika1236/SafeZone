import 'package:flutter/material.dart';
import 'package:safezone_app/citizen/emergency_contacts_screen.dart';
import 'package:safezone_app/models/patrol_assignment.dart';
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

  void sosPreview() {
    showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
              icon: const Icon(Icons.warning_amber_rounded,
                  color: SafeZoneTheme.danger, size: 42),
              title: const Text('SOS dispatch coming next'),
              content: Text(currentPosition == null
                  ? 'Stage 12 does not create SOS requests. Check location first. Emergency dispatch will be connected in Stage 13.'
                  : 'Your location is ready. Stage 12 intentionally does not submit an SOS; dispatch will be implemented in Stage 13.'),
              actions: [
                FilledButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Understood'))
              ],
            ));
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
                  onTap: sosPreview,
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
        const Text('SOS dispatch is not active in this stage.',
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
          title: const Text('Emergency status'),
          subtitle: const Text('No active emergency'),
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
