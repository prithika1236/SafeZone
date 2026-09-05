import 'package:flutter/material.dart';
import 'package:safezone_app/police/police_login_screen.dart';
import 'package:safezone_app/services/session_controller.dart';
import 'package:safezone_app/shared/widgets.dart';

class CitizenAuthScreen extends StatefulWidget {
  const CitizenAuthScreen({super.key, required this.session});
  final SessionController session;

  @override
  State<CitizenAuthScreen> createState() => _CitizenAuthScreenState();
}

class _CitizenAuthScreenState extends State<CitizenAuthScreen> {
  final name = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  bool registering = false;

  @override
  void dispose() {
    name.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    FocusScope.of(context).unfocus();
    if (email.text.trim().isEmpty ||
        password.text.length < 12 ||
        (registering && name.text.trim().length < 2)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text(
            'Enter a valid name, email, and password of at least 12 characters.'),
      ));
      return;
    }
    if (registering) {
      await widget.session
          .registerCitizen(name.text, email.text, password.text);
    } else {
      await widget.session.citizenLogin(email.text, password.text);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SafeZoneLogo(),
                      const SizedBox(height: 34),
                      Text(
                          registering
                              ? 'Create citizen account'
                              : 'Citizen sign in',
                          style: Theme.of(context)
                              .textTheme
                              .headlineMedium
                              ?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 8),
                      const Text(
                          'Access emergency assistance without exposing police deployment information.'),
                      const SizedBox(height: 24),
                      if (registering) ...[
                        TextField(
                            controller: name,
                            textInputAction: TextInputAction.next,
                            decoration:
                                const InputDecoration(labelText: 'Full name')),
                        const SizedBox(height: 14),
                      ],
                      TextField(
                          controller: email,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          decoration:
                              const InputDecoration(labelText: 'Email')),
                      const SizedBox(height: 14),
                      TextField(
                          controller: password,
                          obscureText: true,
                          decoration: const InputDecoration(
                              labelText: 'Password (12+ characters)')),
                      if (widget.session.errorMessage != null) ...[
                        const SizedBox(height: 14),
                        ErrorNotice(widget.session.errorMessage!),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: widget.session.refreshing ? null : submit,
                        child: Text(widget.session.refreshing
                            ? 'Please wait…'
                            : registering
                                ? 'Register securely'
                                : 'Sign in'),
                      ),
                      TextButton(
                        onPressed: () =>
                            setState(() => registering = !registering),
                        child: Text(registering
                            ? 'Already registered? Sign in'
                            : 'New citizen? Create account'),
                      ),
                      const Divider(height: 30),
                      OutlinedButton.icon(
                        onPressed: () =>
                            Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => PoliceLoginScreen(
                              session: widget.session, popOnSuccess: true),
                        )),
                        icon: const Icon(Icons.local_police_outlined),
                        label: const Text('Police officer sign in'),
                      ),
                    ]),
              ),
            ),
          ),
        ),
      );
}
