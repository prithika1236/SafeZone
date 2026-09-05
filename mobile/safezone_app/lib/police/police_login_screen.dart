import 'package:flutter/material.dart';
import 'package:safezone_app/services/session_controller.dart';
import 'package:safezone_app/shared/theme.dart';
import 'package:safezone_app/shared/widgets.dart';

class PoliceLoginScreen extends StatefulWidget {
  const PoliceLoginScreen(
      {required this.session, this.popOnSuccess = false, super.key});
  final SessionController session;
  final bool popOnSuccess;
  @override
  State<PoliceLoginScreen> createState() => _PoliceLoginScreenState();
}

class _PoliceLoginScreenState extends State<PoliceLoginScreen> {
  final formKey = GlobalKey<FormState>();
  final email = TextEditingController();
  final password = TextEditingController();
  bool obscure = true;

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!formKey.currentState!.validate()) return;
    final success = await widget.session.login(email.text, password.text);
    if (!mounted) return;
    if (success && widget.popOnSuccess) {
      Navigator.of(context).pop();
    } else {
      setState(() {});
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
                child: Form(
                  key: formKey,
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const SafeZoneLogo(),
                        const SizedBox(height: 52),
                        const Text('POLICE OPERATIONS',
                            style: TextStyle(
                                color: SafeZoneTheme.blue,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.2,
                                fontSize: 12)),
                        const SizedBox(height: 8),
                        Text('Ready for duty?',
                            style: Theme.of(context)
                                .textTheme
                                .headlineLarge
                                ?.copyWith(
                                    fontWeight: FontWeight.w800,
                                    color: SafeZoneTheme.navy)),
                        const SizedBox(height: 8),
                        const Text(
                            'Sign in with your authorized police account to view today’s deployment.',
                            style: TextStyle(
                                color: Color(0xFF667085), height: 1.5)),
                        const SizedBox(height: 28),
                        if (widget.session.errorMessage
                            case final message?) ...[
                          ErrorNotice(message),
                          const SizedBox(height: 16)
                        ],
                        TextFormField(
                            controller: email,
                            keyboardType: TextInputType.emailAddress,
                            autofillHints: const [AutofillHints.username],
                            decoration: const InputDecoration(
                                labelText: 'Email address',
                                prefixIcon: Icon(Icons.badge_outlined)),
                            validator: (value) =>
                                value == null || !value.contains('@')
                                    ? 'Enter a valid email address'
                                    : null),
                        const SizedBox(height: 16),
                        TextFormField(
                            controller: password,
                            obscureText: obscure,
                            autofillHints: const [AutofillHints.password],
                            decoration: InputDecoration(
                                labelText: 'Password',
                                prefixIcon: const Icon(Icons.lock_outline),
                                suffixIcon: IconButton(
                                    onPressed: () =>
                                        setState(() => obscure = !obscure),
                                    icon: Icon(obscure
                                        ? Icons.visibility_outlined
                                        : Icons.visibility_off_outlined))),
                            validator: (value) => value == null || value.isEmpty
                                ? 'Password is required'
                                : null,
                            onFieldSubmitted: (_) => submit()),
                        const SizedBox(height: 22),
                        FilledButton(
                            onPressed:
                                widget.session.refreshing ? null : submit,
                            child: widget.session.refreshing
                                ? const SizedBox.square(
                                    dimension: 22,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2, color: Colors.white))
                                : const Text('Sign in securely')),
                        const SizedBox(height: 22),
                        const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.verified_user_outlined,
                                  size: 17, color: Color(0xFF667085)),
                              SizedBox(width: 7),
                              Text('Authorized POLICE accounts only',
                                  style: TextStyle(
                                      color: Color(0xFF667085), fontSize: 12))
                            ]),
                      ]),
                ),
              ),
            ),
          ),
        ),
      );
}
