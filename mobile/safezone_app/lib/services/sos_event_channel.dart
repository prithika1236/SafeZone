import 'dart:convert';

import 'package:safezone_app/services/api_client.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class SOSEventChannel {
  SOSEventChannel(this.api);
  final ApiClient api;
  WebSocketChannel? _channel;

  Future<Stream<Map<String, dynamic>>> connect() async {
    final token = await api.accessToken();
    if (token == null) {
      throw const ApiException('Your session has expired.', statusCode: 401);
    }
    final channel = WebSocketChannel.connect(Uri.parse(api.sosWebSocketUrl));
    _channel = channel;
    channel.sink.add(jsonEncode({'access_token': token}));
    return channel.stream.map(
      (event) => jsonDecode(event as String) as Map<String, dynamic>,
    );
  }

  void close() {
    _channel?.sink.close();
    _channel = null;
  }
}
