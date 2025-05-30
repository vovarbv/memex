// lib/config.dart

/// Application-wide constants
class AppConstants {
  // static const String supabaseUrl = 'http://51.222.11.80:8000';
  // static const String supabaseUrl = 'http://localhost:8000';
  static const String supabaseUrl = 'http://185.15.45.226:6001';

  static const String supabaseKey =
      'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsImlhdCI6MTczOTgwODU2NiwiZXhwIjoxODExODA4NTY2fQ.u4ABKpNBc7HpBOTSIza2gpxf5UHGATri-NhjmM5CbVE';

  // Server configuration
  // static const String serverBaseUrl = 'http://51.222.11.80:8000';
  // static const String serverBaseUrl = 'http://localhost:8000';
  static const String serverBaseUrl = 'http://185.15.45.226:6001';

  // Storage URL configuration
  static const bool useFixedStorageUrls =
      true; // Enables the fix for storage URL format
  static const bool useOriginalSupabaseUrls =
      true; // Use URLs exactly as returned by Supabase with no modification

  // Cache durations
  static const int defaultCacheDurationHours = 24;
  static const int imageCacheDurationDays = 7;
  static const int criticalDataCacheDurationDays = 30;

  // Sync intervals
  static const int syncIntervalMinutes = 30;
  static const int backgroundSyncIntervalHours = 12;

  // Security
  static const bool useSecureStorage = true;
  static const int sessionTimeoutMinutes = 60;

  // Network
  static const int requestTimeoutSeconds = 10;
  static const int maxRetryAttempts = 3;
}
