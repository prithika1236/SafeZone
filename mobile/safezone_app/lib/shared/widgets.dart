import 'package:flutter/material.dart';

class SafeZoneLogo extends StatelessWidget {
  const SafeZoneLogo({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: compact ? 38 : 52,
            height: compact ? 38 : 52,
            decoration: BoxDecoration(
              color: const Color(0xFF2563EB),
              borderRadius: BorderRadius.circular(compact ? 10 : 15),
            ),
            alignment: Alignment.center,
            child: Text('SZ', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: compact ? 12 : 16)),
          ),
          const SizedBox(width: 12),
          const Text('SAFEZONE', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5)),
        ],
      );
}

class ErrorNotice extends StatelessWidget {
  const ErrorNotice(this.message, {super.key});
  final String message;
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(color: const Color(0xFFFFEDEA), borderRadius: BorderRadius.circular(12)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.error_outline, color: Color(0xFFB42318), size: 20),
          const SizedBox(width: 9),
          Expanded(child: Text(message, style: const TextStyle(color: Color(0xFF912018)))),
        ]),
      );
}

String formatDateTime(DateTime value) {
  final local = value.toLocal();
  String two(int number) => number.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year}  ${two(local.hour)}:${two(local.minute)}';
}

String shortId(String value) => value.length > 8 ? '${value.substring(0, 8)}…' : value;
