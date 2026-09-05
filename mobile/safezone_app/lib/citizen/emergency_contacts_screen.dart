import 'package:flutter/material.dart';
import 'package:safezone_app/models/emergency_contact.dart';
import 'package:safezone_app/services/api_client.dart';
import 'package:safezone_app/shared/widgets.dart';

class EmergencyContactsScreen extends StatefulWidget {
  const EmergencyContactsScreen({super.key, required this.api});
  final ApiClient api;
  @override
  State<EmergencyContactsScreen> createState() =>
      _EmergencyContactsScreenState();
}

class _EmergencyContactsScreenState extends State<EmergencyContactsScreen> {
  List<EmergencyContact> contacts = [];
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      contacts = await widget.api.emergencyContacts();
    } on ApiException catch (exception) {
      error = exception.message;
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> edit([EmergencyContact? contact]) async {
    final changed = await showDialog<bool>(
        context: context,
        builder: (_) => _ContactDialog(api: widget.api, contact: contact));
    if (changed == true) await load();
  }

  Future<void> remove(EmergencyContact contact) async {
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              title: const Text('Remove contact?'),
              content: Text(
                  '${contact.name} will no longer appear in your emergency contacts.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Keep')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Remove'))
              ],
            ));
    if (confirmed != true) return;
    try {
      await widget.api.deleteEmergencyContact(contact.id);
      await load();
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Emergency contacts')),
        floatingActionButton: FloatingActionButton.extended(
            onPressed: () => edit(),
            icon: const Icon(Icons.person_add),
            label: const Text('Add')),
        body: RefreshIndicator(
            onRefresh: load,
            child: ListView(padding: const EdgeInsets.all(20), children: [
              const Text('Only you can view and manage these contacts.'),
              const SizedBox(height: 16),
              if (error != null) ...[
                ErrorNotice(error!),
                const SizedBox(height: 12)
              ],
              if (loading)
                const Center(
                    child: Padding(
                        padding: EdgeInsets.all(30),
                        child: CircularProgressIndicator()))
              else if (contacts.isEmpty)
                const Card(
                    child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                            'No emergency contacts yet. Add someone you trust.')))
              else
                ...contacts.map((contact) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                        child: ListTile(
                      leading:
                          const CircleAvatar(child: Icon(Icons.person_outline)),
                      title: Text(contact.name),
                      subtitle: Text([
                        contact.relationshipLabel,
                        contact.phoneNumber
                      ].whereType<String>().join(' • ')),
                      trailing: PopupMenuButton<String>(
                          onSelected: (value) =>
                              value == 'edit' ? edit(contact) : remove(contact),
                          itemBuilder: (_) => const [
                                PopupMenuItem(
                                    value: 'edit', child: Text('Edit')),
                                PopupMenuItem(
                                    value: 'delete', child: Text('Delete'))
                              ]),
                    )))),
              const SizedBox(height: 80),
            ])),
      );
}

class _ContactDialog extends StatefulWidget {
  const _ContactDialog({required this.api, this.contact});
  final ApiClient api;
  final EmergencyContact? contact;
  @override
  State<_ContactDialog> createState() => _ContactDialogState();
}

class _ContactDialogState extends State<_ContactDialog> {
  late final name = TextEditingController(text: widget.contact?.name);
  late final phone = TextEditingController(text: widget.contact?.phoneNumber);
  late final relationship =
      TextEditingController(text: widget.contact?.relationshipLabel);
  String? error;
  bool saving = false;
  @override
  void dispose() {
    name.dispose();
    phone.dispose();
    relationship.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (name.text.trim().length < 2 || phone.text.trim().length < 8) {
      setState(() => error = 'Enter a valid name and phone number.');
      return;
    }
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.api.saveEmergencyContact(
          id: widget.contact?.id,
          name: name.text,
          phoneNumber: phone.text,
          relationshipLabel: relationship.text);
      if (mounted) {
        Navigator.pop(context, true);
      }
    } on ApiException catch (exception) {
      if (mounted) {
        setState(() {
          saving = false;
          error = exception.message;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(widget.contact == null
            ? 'Add emergency contact'
            : 'Edit emergency contact'),
        content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(
              controller: name,
              decoration: const InputDecoration(labelText: 'Name')),
          const SizedBox(height: 12),
          TextField(
              controller: phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Phone number')),
          const SizedBox(height: 12),
          TextField(
              controller: relationship,
              decoration:
                  const InputDecoration(labelText: 'Relationship (optional)')),
          if (error != null) ...[
            const SizedBox(height: 12),
            ErrorNotice(error!)
          ],
        ])),
        actions: [
          TextButton(
              onPressed: saving ? null : () => Navigator.pop(context),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: saving ? null : save,
              child: Text(saving ? 'Saving…' : 'Save'))
        ],
      );
}
