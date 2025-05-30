import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'data/offline/data_sync_service.dart';
import 'data/service_locator.dart';
import 'features/auth/presentation/bloc/auth_cubit.dart' as app_auth;
import 'features/auth/presentation/pages/authorization_choice_page.dart';
import 'features/items/domain/repositories/items_repository.dart';
import 'features/items/presentation/pages/item_details_page.dart';
import 'features/language/presentation/bloc/language_cubit.dart';
import 'features/products/domain/repositories/product_repository.dart';
import 'features/products/presentation/bloc/products_cubit.dart';
import 'features/products/presentation/pages/client_home_page.dart';
import 'features/service/domain/repositories/service_repository.dart';
import 'features/service/presentation/pages/change_item_page.dart';
import 'features/service/presentation/pages/close_case_page.dart';
// New service action pages:
import 'features/service/presentation/pages/create_case_page.dart';
import 'features/service/presentation/pages/process_case_page.dart';
import 'features/service/presentation/pages/replace_item_page.dart';
import 'features/service/presentation/pages/service_home_page.dart';
import 'features/service/presentation/pages/service_logs_page.dart';
import 'features/service/presentation/pages/service_replacements_page.dart';
import 'features/service/presentation/pages/write_log_page.dart';
import 'features/service/presentation/pages/service_case_list_page.dart';
import 'features/service/presentation/bloc/service_case_filter_cubit.dart';
import 'features/service/presentation/bloc/service_cases_cubit.dart';
import 'features/language/data/translation_service.dart';
import 'l10n/app_localizations.dart';
import 'theme/app_theme.dart';
import 'widgets/app_scaffold.dart';

// Create a custom delegate for AppLocalizations
class CustomAppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const CustomAppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) {
    return ['en', 'es', 'fr', 'de', 'pl', 'zh', 'uk', 'ru']
        .contains(locale.languageCode);
  }

  @override
  Future<AppLocalizations> load(Locale locale) async {
    return AppLocalizations(locale);
  }

  @override
  bool shouldReload(LocalizationsDelegate<AppLocalizations> old) => false;
}

// Authentication guard for protected routes
class AuthGuard {
  static Widget protect(BuildContext context, Widget child) {
    // Get the AuthCubit
    final authCubit = context.read<app_auth.AuthCubit>();

    // If already authenticated, return the child immediately
    if (authCubit.state is app_auth.Authenticated) {
      return child;
    }

    // If not authenticated, force a check and redirect if still not authenticated
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // Check auth status directly - this will try to restore the session
      final isAuthenticated = await authCubit.checkAuthStatus();

      if (!isAuthenticated && context.mounted) {
        // Navigate to authorization page
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const AuthorizationChoicePage()),
          (route) => false,
        );
      }
    });

    // Show a loading indicator while checking
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(AppLocalizations.of(context)
                    ?.translate('checkingAuthentication') ??
                'Checking authentication...'),
          ],
        ),
      ),
    );
  }

  // Use this method for routes that modify data
  static Widget protectWithValidation(BuildContext context, Widget child) {
    // Get the AuthCubit
    final authCubit = context.read<app_auth.AuthCubit>();

    // If already authenticated, check if we need credential validation
    if (authCubit.state is app_auth.Authenticated) {
      // Schedule credential validation if needed, but don't block UI
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        await authCubit.validateCredentialsForTransaction();
      });

      return child;
    }

    // If not authenticated at all, use standard protection
    return protect(context, child);
  }
}

// Add an InitialAuthenticationRouter to handle initial authentication state
class InitialAuthenticationRouter extends StatefulWidget {
  const InitialAuthenticationRouter({super.key});

  @override
  State<InitialAuthenticationRouter> createState() =>
      _InitialAuthenticationRouterState();
}

class _InitialAuthenticationRouterState
    extends State<InitialAuthenticationRouter> {
  bool _attemptedRestore = false;
  bool _isSyncing = false;
  double _syncProgress = 0.0;
  late StreamSubscription<double>? _syncStreamSubscription;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _restoreSessionAndSync();
    });

    // Listen to sync progress from DataSyncService
    final dataSyncService = serviceLocator<DataSyncService>();
    _syncStreamSubscription = dataSyncService.syncProgressStream.listen((progress) {
      if (mounted) {
        // This listener primarily updates the progress value.
        // It also sets _isSyncing to true if progress is happening and not yet 1.0.
        // This helps keep the sync UI visible if DataSyncService is actively pushing updates.
        bool stillSyncing = progress < 1.0 && progress >= 0.0; // Consider 0.0 as potentially starting
        if (_isSyncing != stillSyncing || _syncProgress != progress) {
            debugPrint('App_InitialAuthRouter (StreamListener): Sync progress update: $progress, Setting _isSyncing = $stillSyncing');
            setState(() {
                _syncProgress = progress;
                _isSyncing = stillSyncing;
            });
        }
      }
    });
  }

  @override
  void dispose() {
    _syncStreamSubscription?.cancel();
    super.dispose();
  }

  // Try to restore a previously saved session
  Future<void> _restoreSessionAndSync() async {
    if (_attemptedRestore) {
      debugPrint('App_InitialAuthRouter: _restoreSessionAndSync called but already attempted. Skipping.');
      return;
    }
    _attemptedRestore = true;
    debugPrint('App_InitialAuthRouter: _restoreSessionAndSync started. Will observe auth and sync state.');

    final authCubit = context.read<app_auth.AuthCubit>();
    final dataSyncService = serviceLocator<DataSyncService>();

    // AuthService.initialize() in main.dart should have already attempted session restoration.
    // We need to ensure AuthCubit reflects the outcome of that.
    debugPrint('App_InitialAuthRouter: Calling AuthCubit.checkCurrentAuthStatus() to ensure cubit state is up-to-date.');
    await authCubit.checkCurrentAuthStatus(); // This updates the cubit based on the underlying auth state
    debugPrint('App_InitialAuthRouter: Current AuthCubit state after check: ${authCubit.state}');

    if (authCubit.state is app_auth.Authenticated) {
      debugPrint('App_InitialAuthRouter: User IS Authenticated (via AuthCubit). Preparing to display sync status if applicable.');
      // At this point, AuthService.initialize() in main.dart should have also called
      // DataSyncService.performInitialSync() if the user was authenticated there.
      // So, DataSyncService might already be syncing.

      // We need to set the widget's _isSyncing state based on DataSyncService's actual current state.
      bool actualDsIsSyncing = dataSyncService.isSyncing;
      double actualDsProgress = dataSyncService.currentProgress;

      debugPrint('App_InitialAuthRouter: DataSyncService current status - isSyncing: $actualDsIsSyncing, progress: $actualDsProgress');

      if (actualDsIsSyncing || (actualDsProgress > 0.0 && actualDsProgress < 1.0) ) {
        // If DataSyncService reports it is syncing, or its progress suggests it has been active.
        if (mounted) {
          debugPrint('App_InitialAuthRouter: Setting widget state: _isSyncing = true, _syncProgress = $actualDsProgress');
          setState(() {
            _isSyncing = true; // This widget should show the syncing UI
            _syncProgress = actualDsProgress;
          });
        }
      } else {
        // DataSyncService is not actively syncing (or progress is 0 or 1.0).
        // The UI should not show the sync-specific loading for this widget.
        // The stream listener will still update progress if DataSyncService starts/continues syncing later.
        if (mounted) {
          debugPrint('App_InitialAuthRouter: Setting widget state: _isSyncing = false (DataSyncService not actively mid-sync).');
          setState(() {
            _isSyncing = false;
          });
        }
      }
    } else {
      debugPrint('App_InitialAuthRouter: User is NOT Authenticated (via AuthCubit). Sync UI not applicable from here.');
      if (mounted) {
        // Ensure UI doesn't think it's syncing if auth failed.
        setState(() {
          _isSyncing = false;
        });
      }
    }
    debugPrint('App_InitialAuthRouter: _restoreSessionAndSync observation phase finished.');
  }

  @override
  Widget build(BuildContext context) {
    // Show loading indicator while checking authentication and syncing data
    if (!_attemptedRestore || _isSyncing) {
      final localizations = AppLocalizations.of(context);
      String message = '';
      double progress = 0.0;

      if (!_attemptedRestore) {
        message = localizations?.translate('loading') ?? 'Loading...';
        progress = 0.1;
      } else if (_isSyncing) {
        message = localizations?.translate('syncingData') ?? 'Syncing data...';
        progress = _syncProgress;
      }

      return MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.lightTheme,
        themeMode: ThemeMode.system,
        localizationsDelegates: const [
          CustomAppLocalizationsDelegate(),
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: const [
          Locale('en'), Locale('es'), Locale('fr'), Locale('de'),
          Locale('pl'), Locale('zh'), Locale('uk'), Locale('ru'),
        ],
        locale: Localizations.maybeLocaleOf(context) ?? const Locale('pl'),
        home: AppScaffold(
          isAuthenticated: false,
          extendBodyBehindAppBar: false,
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Padding(
                  padding: const EdgeInsets.all(32.0),
                  child: Image.asset(
                      'assets/images/logo_round_blue_inside_without_background_1024x1024.png',
                      height: 260),
                ),
                Text(message, style: const TextStyle(fontSize: 16)),
                const SizedBox(height: 24),
                SizedBox(
                  width: 200,
                  child: LinearProgressIndicator(value: progress),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return BlocBuilder<app_auth.AuthCubit, app_auth.AuthState>(
      builder: (context, state) {
        final localizations = AppLocalizations.of(context);

        // If syncing data after authentication, show progress
        if (_isSyncing && state is app_auth.Authenticated) {
          return AppScaffold(
            isAuthenticated: false,
            extendBodyBehindAppBar: false,
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 16),
                  Text(localizations?.format('syncingDataPercent', [(_syncProgress * 100).toInt().toString()]) ?? 'Syncing data (${(_syncProgress * 100).toInt()}%)'),
                ],
              ),
            ),
          );
        }

        // If already authenticated, route to the appropriate home page based on role
        if (state is app_auth.Authenticated) {
          final user = state.user;
          
          // Log for debugging purposes
          debugPrint('Authenticated user role: ${user.role}, role ID: ${user.role.index}');
          
          // Determine home page based on role
          if (user.role == app_auth.UserRole.service || user.role == app_auth.UserRole.god) {
            // For service or admin users, go to service page
            return BlocProvider<LanguageCubit>.value(
              value: context.read<LanguageCubit>(),
              child: const ServiceHomePage(itemId: null),
            );
          } else {
            // For regular clients, go to client home
            return const ClientHomePage();
          }
        }

        // If in loading state, show progress indicator
        if (state is app_auth.AuthLoading) {
          return const AppScaffold(
            isAuthenticated: false,
            extendBodyBehindAppBar: false,
            body: Center(child: CircularProgressIndicator()),
          );
        }

        // Otherwise, go to authorization choice
        return const AuthorizationChoicePage();
      },
    );
  }
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // Add a GlobalKey for ScaffoldMessenger
  static final GlobalKey<ScaffoldMessengerState> _scaffoldMessengerKey =
      GlobalKey<ScaffoldMessengerState>();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<LanguageCubit, Locale>(
      builder: (context, locale) {
        return MaterialApp(
          title: 'Maintain',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.lightTheme,
          themeMode: ThemeMode.system,
          scaffoldMessengerKey: _scaffoldMessengerKey,
          locale: locale,
          supportedLocales: const [
            Locale('en'),
            Locale('es'),
            Locale('fr'),
            Locale('de'),
            Locale('pl'),
            Locale('zh'),
            Locale('uk'),
            Locale('ru'),
          ],
          localizationsDelegates: const [
            CustomAppLocalizationsDelegate(),
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          localeResolutionCallback: (locale, supportedLocales) {
            if (locale == null || !supportedLocales.contains(locale)) {
              return const Locale('pl');
            }
            return locale;
          },
          builder: (context, child) {
            return MediaQuery(
              data: MediaQuery.of(context).copyWith(
                textScaler: MediaQuery.textScalerOf(context)
                    .clamp(minScaleFactor: 0.8, maxScaleFactor: 1.2),
              ),
              child: MultiBlocListener(
                listeners: [
                  BlocListener<app_auth.AuthCubit, app_auth.AuthState>(
                    listener: (context, state) {
                      if (state is app_auth.AuthError) {
                        final localizations = AppLocalizations.of(context);
                        String displayMessage = state.message;
                        if (!state.message.contains(' ') && (state.message.contains(RegExp(r'[A-Z]')) || state.message.contains('_'))) {
                            displayMessage = localizations?.translate(state.message) ?? state.message;
                        }
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(displayMessage)),
                        );
                      }
                    },
                  ),
                ],
                child: Container(
                  constraints: const BoxConstraints(
                    minWidth: 400,
                    minHeight: 500,
                  ),
                  child: child!,
                ),
              ),
            );
          },
          initialRoute: '/',
          routes: {
            // Unprotected routes - change initial route to use the router
            '/': (context) => const InitialAuthenticationRouter(),
            '/auth': (context) => const AuthorizationChoicePage(),

            // Protected routes that require authentication
            '/service-cases': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : 'all'; // Default to 'all'
              // Protect the route and wrap with MultiProvider
              return AuthGuard.protect(
                context,
                MultiProvider(
                  providers: [
                    Provider<ServiceRepository>(
                        create: (_) => serviceLocator<ServiceRepository>()),
                    Provider<ItemsRepository>(
                        create: (_) => serviceLocator<ItemsRepository>()),
                    Provider<TranslationService>(
                        create: (_) => serviceLocator<TranslationService>()),
                    BlocProvider<ServiceCasesCubit>(
                        create: (_) => ServiceCasesCubit(
                            serviceLocator<ServiceRepository>())),
                    BlocProvider<ServiceCaseFilterCubit>(
                        create: (_) => ServiceCaseFilterCubit()),
                  ],
                  child: ServiceCaseListPage(itemId: itemId),
                ),
              );
            },
            '/replacements': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protect(
                  context, ServiceReplacementsPage(itemId: itemId));
            },
            '/service-logs': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protect(
                  context, ServiceLogsPage(itemId: itemId));
            },
            '/create-service-case': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protectWithValidation(
                  context, CreateCasePage(itemId: itemId));
            },
            '/process-case': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              String itemId = '';
              String? caseId;

              if (args is String) {
                itemId = args;
              } else if (args is Map<String, String>) {
                itemId = args['itemId'] ?? '';
                caseId = args['caseId'];
              }

              return AuthGuard.protectWithValidation(
                  context, ProcessCasePage(itemId: itemId, caseId: caseId));
            },
            '/close-case': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              String itemId = '';
              String? caseId;

              if (args is String) {
                itemId = args;
              } else if (args is Map<String, String>) {
                itemId = args['itemId'] ?? '';
                caseId = args['caseId'];
              }

              return AuthGuard.protectWithValidation(
                  context, CloseCasePage(itemId: itemId, caseId: caseId));
            },
            '/replace-item': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protectWithValidation(
                  context, ReplaceItemPage(itemId: itemId));
            },
            '/change-item': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protectWithValidation(
                  context, ChangeItemPage(itemId: itemId));
            },
            '/write-log': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protectWithValidation(
                  context, WriteLogPage(itemId: itemId));
            },
            '/item-details': (context) {
              final args = ModalRoute.of(context)?.settings.arguments;
              final itemId = args is String ? args : '';
              return AuthGuard.protect(
                  context,
                  MultiProvider(
                    providers: [
                      Provider<ItemsRepository>(
                        create: (_) => serviceLocator<ItemsRepository>(),
                      ),
                      Provider<ServiceRepository>(
                        create: (_) => serviceLocator<ServiceRepository>(),
                      ),
                      BlocProvider<ProductsCubit>(
                        create: (_) =>
                            ProductsCubit(serviceLocator<ProductRepository>()),
                      ),
                      // Provide LanguageCubit for language changes
                      BlocProvider<LanguageCubit>.value(
                        value: context.read<LanguageCubit>(),
                      ),
                    ],
                    child: ItemDetailsPage(itemId: itemId),
                  ));
            },
          },
        );
      },
    );
  }
}
