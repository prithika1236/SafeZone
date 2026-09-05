import 'package:flutter/material.dart';
import 'package:safezone_app/police/police_home_screen.dart';
import 'package:safezone_app/police/police_login_screen.dart';
import 'package:safezone_app/services/session_controller.dart';
import 'package:safezone_app/shared/theme.dart';

void main() => runApp(const SafeZoneApp());

class SafeZoneApp extends StatefulWidget {
  const SafeZoneApp({super.key, this.sessionController});
  final SessionController? sessionController;

  @override
  State<SafeZoneApp> createState() => _SafeZoneAppState();
}

class _SafeZoneAppState extends State<SafeZoneApp> {
  late final SessionController session = widget.sessionController ?? SessionController();

  @override
  void initState() {
    super.initState();
    session.restore();
  }

  @override
  void dispose() {
    if (widget.sessionController == null) session.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'SafeZone Police',
        debugShowCheckedModeBanner: false,
        theme: SafeZoneTheme.light,
        home: ListenableBuilder(
          listenable: session,
          builder: (context, _) => switch (session.status) {
            SessionStatus.restoring => const _StartupScreen(),
            SessionStatus.signedOut => PoliceLoginScreen(session: session),
            SessionStatus.authenticated => PoliceHomeScreen(session: session),
          },
        ),
      );
}

class _StartupScreen extends StatelessWidget {
  const _StartupScreen();
  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.shield_rounded, size: 58, color: SafeZoneTheme.blue),
          SizedBox(height: 20),
          CircularProgressIndicator(),
          SizedBox(height: 14),
          Text('Securing your session…'),
        ])),
      );
}
