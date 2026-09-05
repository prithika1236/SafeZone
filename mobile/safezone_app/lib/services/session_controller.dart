import 'package:flutter/foundation.dart';
import 'package:safezone_app/models/patrol_assignment.dart';
import 'package:safezone_app/models/user_profile.dart';
import 'package:safezone_app/services/api_client.dart';

enum SessionStatus { restoring, signedOut, authenticated }

class SessionController extends ChangeNotifier {
  SessionController({ApiClient? apiClient}) : api = apiClient ?? ApiClient();

  final ApiClient api;
  SessionStatus status = SessionStatus.restoring;
  UserProfile? profile;
  PatrolAssignment? assignment;
  String? errorMessage;
  bool refreshing = false;

  Future<void> restore() async {
    try {
      final user = await api.currentUser();
      if (user.role != 'POLICE' && user.role != 'CITIZEN') {
        throw const ApiException(
            'This role is not available in the mobile application.');
      }
      profile = user;
      status = SessionStatus.authenticated;
      if (user.role == 'POLICE') await refreshAssignment(silent: true);
    } on Exception {
      await api.logout();
      status = SessionStatus.signedOut;
    }
    notifyListeners();
  }

  Future<bool> login(String email, String password) async {
    errorMessage = null;
    refreshing = true;
    notifyListeners();
    try {
      profile = await api.loginForRole(email, password, expectedRole: 'POLICE');
      status = SessionStatus.authenticated;
      assignment = await api.currentAssignment();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      refreshing = false;
      notifyListeners();
    }
  }

  Future<bool> citizenLogin(String email, String password) async =>
      _citizenAuthentication(
          () => api.loginForRole(email, password, expectedRole: 'CITIZEN'));

  Future<bool> registerCitizen(
          String name, String email, String password) async =>
      _citizenAuthentication(() => api.registerCitizen(name, email, password));

  Future<bool> _citizenAuthentication(
      Future<UserProfile> Function() authenticate) async {
    errorMessage = null;
    refreshing = true;
    notifyListeners();
    try {
      profile = await authenticate();
      assignment = null;
      status = SessionStatus.authenticated;
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      refreshing = false;
      notifyListeners();
    }
  }

  Future<void> refreshAssignment({bool silent = false}) async {
    if (!silent) {
      refreshing = true;
      errorMessage = null;
      notifyListeners();
    }
    try {
      assignment = await api.currentAssignment();
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        await logout();
      } else {
        errorMessage = error.message;
      }
    } finally {
      refreshing = false;
      notifyListeners();
    }
  }

  Future<bool> transition(String action) async {
    final current = assignment;
    if (current == null) return false;
    refreshing = true;
    errorMessage = null;
    notifyListeners();
    try {
      assignment = await api.transition(current.id, action);
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      if (error.statusCode == 401) await logout();
      return false;
    } finally {
      refreshing = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    await api.logout();
    profile = null;
    assignment = null;
    errorMessage = null;
    status = SessionStatus.signedOut;
    notifyListeners();
  }
}
