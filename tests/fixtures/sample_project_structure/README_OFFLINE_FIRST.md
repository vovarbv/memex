# Maintain - Offline-First Architecture

This document outlines the offline-first architecture implemented in the Maintain application. This design ensures that
the app works seamlessly in both online and offline modes, with data synchronization when connectivity is restored.

## Architecture Overview

The application follows a clean architecture approach with clear separation between:

- **Domain Layer**: Contains business entities and repository interfaces
- **Data Layer**: Contains data sources and repository implementations
- **Presentation Layer**: Contains UI components and state management (BLoC)

### Key Components

1. **Repository Pattern**
    - Repository interfaces abstract data access operations
    - Repository implementations combine remote and local data sources
    - The app always tries to use remote data first, falling back to local data when offline

2. **Dual Data Sources**
    - `SupabaseAuthDataSource`: Handles remote authentication via Supabase
    - `LocalAuthDataSource`: Handles offline authentication via cached data

3. **Connectivity Management**
    - `ConnectivityService`: Monitors network connectivity changes
    - Provides helpers for executing operations with connectivity awareness

4. **Offline Data Storage**
    - SQLite local database (using drift)
    - SharedPreferences for simple key-value storage
    - Structured caching of user data and sessions

5. **Synchronization**
    - `SyncOperationManager`: Queues operations performed offline
    - Processes queue when connectivity is restored
    - Handles conflict resolution

## Data Flow

1. **Authentication Flow**
    - App tries to authenticate with Supabase
    - If successful, user data is cached locally
    - If offline, app falls back to locally cached credentials

2. **Data Access Flow**
    - App first checks network connectivity
    - If online, it attempts to retrieve data from Supabase
    - If offline or if remote operation fails, it falls back to local cache

3. **Data Modification Flow**
    - If online, changes are sent directly to Supabase
    - If offline, changes are stored locally and queued for future synchronization
    - When connectivity is restored, queued changes are processed

## Implementation Details

### User Authentication

Authentication is handled through the `AuthRepository` interface, with its implementation combining both remote and
local authentication:

```dart
Future<User?> getCurrentUser() async {
  final userData = await _tryRemoteOrLocal(
    () => _remoteDataSource.getCurrentUser(),
    () => _localDataSource.getCurrentUser(),
  );
  
  return userData != null ? User.fromJson(userData) : null;
}
```

### Remote/Local Fallback Strategy

The `_tryRemoteOrLocal` helper method in repositories encapsulates the common pattern of trying remote operations first
and falling back to local:

```dart
Future<T?> _tryRemoteOrLocal<T>(
  Future<T?> Function() remoteOperation,
  Future<T?> Function() localOperation,
) async {
  if (await _connectivityService.isConnected()) {
    try {
      final result = await remoteOperation();
      return result;
    } catch (e) {
      // Fall back to local operation
      return localOperation();
    }
  } else {
    // Execute local operation directly if offline
    return localOperation();
  }
}
```

### Data Caching

Data is cached locally during online operations to ensure it's available when offline:

```dart
Future<void> cacheUserData(Map<String, dynamic> userData) async {
  try {
    final prefs = await SharedPreferences.getInstance();
    
    // Get existing cached users
    List<dynamic> cachedUsers = [];
    final cachedUsersJson = prefs.getString(_userCacheKey);
    if (cachedUsersJson != null) {
      cachedUsers = json.decode(cachedUsersJson);
    }
    
    // Update or add the user
    final userIndex = cachedUsers.indexWhere((user) => user['id'] == userData['id']);
    if (userIndex >= 0) {
      cachedUsers[userIndex] = userData;
    } else {
      cachedUsers.add(userData);
    }
    
    // Save updated cache
    await prefs.setString(_userCacheKey, json.encode(cachedUsers));
  } catch (e) {
    debugPrint('Error caching user data: $e');
  }
}
```

## Best Practices

1. **Preload Essential Data**
    - When the user logs in, preload frequently needed data
    - Cache service cases, items, and user information

2. **Minimize Network Calls**
    - Use cached data whenever appropriate, even when online
    - Implement a cache invalidation strategy (time-based or event-based)

3. **Graceful Error Handling**
    - Always have a fallback plan for network failures
    - Provide clear feedback to users about connectivity status

4. **Data Synchronization**
    - Use timestamps to track when data was last updated
    - Implement conflict resolution for concurrent changes

## Database Tables

To support offline operations, the local database includes these key tables:

- `LocalItems`: Cached items data
- `LocalServiceCases`: Cached service cases
- `LocalServiceHistory`: Cached service history events
- `OfflineItems`: New items created while offline
- `OfflineServiceCases`: New service cases created while offline

## Sync Operations

The `SyncOperationManager` handles synchronization when connectivity is restored:

1. Loads pending operations from local storage
2. Processes each operation in sequence
3. Handles conflicts using the configured strategy
4. Updates local cache with server responses
5. Marks operations as completed when successful

## Future Improvements

1. **Enhanced Conflict Resolution**
    - Implement more sophisticated conflict resolution strategies
    - Add user-facing resolution for complex conflicts

2. **Background Sync**
    - Add capability to sync data in the background
    - Implement periodic sync even when app is not in foreground

3. **Selective Sync**
    - Allow users to choose which data to sync
    - Implement priority-based sync for essential data

4. **Data Compression**
    - Compress cached data to reduce storage footprint
    - Implement efficient diff-based updates 