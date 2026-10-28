import { Rubik_400Regular, Rubik_500Medium, Rubik_600SemiBold, Rubik_700Bold, useFonts } from '@expo-google-fonts/rubik';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useState } from 'react';
import { useColorScheme } from 'react-native';

import { AuthProvider, useAuth } from '@/auth/AuthContext';
import { I18nProvider, useI18n } from '@/i18n/I18nContext';
import { fonts, useColors } from '@/ui/theme';

SplashScreen.preventAutoHideAsync();

function Navigator({ fontsReady }: { fontsReady: boolean }) {
  const { user, ready } = useAuth();
  const { t } = useI18n();
  const c = useColors();

  useEffect(() => {
    if (ready && fontsReady) SplashScreen.hideAsync();
  }, [ready, fontsReady]);
  if (!ready || !fontsReady) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: c.bg },
        headerShadowVisible: false,
        headerTintColor: c.text,
        headerTitleStyle: { fontFamily: fonts['600'], fontSize: 17 },
        contentStyle: { backgroundColor: c.bg },
        headerBackTitle: t('back'),
      }}>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="index" options={{ title: t('myGoals') }} />
        <Stack.Screen name="goals/new" options={{ title: t('newGoal') }} />
        <Stack.Screen name="goal/[id]/index" options={{ title: '' }} />
        <Stack.Screen name="goal/[id]/intake" options={{ title: t('intakeTitle') }} />
        <Stack.Screen name="goal/[id]/chat" options={{ title: t('chat') }} />
        <Stack.Screen name="goal/[id]/settings" options={{ title: t('goalSettings') }} />
        <Stack.Screen name="notifications" options={{ title: t('notifications') }} />
        <Stack.Screen name="settings" options={{ title: t('settings') }} />
      </Stack.Protected>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
        <Stack.Screen name="register" options={{ headerShown: false }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const scheme = useColorScheme();
  const c = useColors();
  const [fontsLoaded, fontError] = useFonts({ Rubik_400Regular, Rubik_500Medium, Rubik_600SemiBold, Rubik_700Bold });
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 5_000 } } }));
  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const navTheme = { ...base, colors: { ...base.colors, background: c.bg, card: c.bg, text: c.text, border: c.border, primary: c.primary } };
  return (
    <ThemeProvider value={navTheme}>
      <QueryClientProvider client={queryClient}>
        <I18nProvider>
          <AuthProvider>
            {/* If the font fails to load, fall back to the system font instead of blocking the app. */}
            <Navigator fontsReady={fontsLoaded || !!fontError} />
          </AuthProvider>
        </I18nProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
