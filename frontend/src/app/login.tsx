import { Link } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import { useI18n } from '@/i18n/I18nContext';
import { AppText, Button, Card, Field, Screen } from '@/ui';
import { LanguageToggle } from '@/ui/LanguageToggle';
import { space, useColors } from '@/ui/theme';

export default function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const c = useColors();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      await login(email.trim(), password);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <View style={{ flex: 1, justifyContent: 'center', paddingVertical: space.xl }}>
        <LanguageToggle />
        <AppText size={30} weight="700" style={{ marginBottom: space.lg }}>
          {t('appName')}
        </AppText>
        <Card>
          <Field label={t('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
          <Field label={t('password')} value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={submit} />
          {error ? <AppText style={{ color: c.danger, marginBottom: space.sm }}>{error}</AppText> : null}
          <Button title={t('login')} onPress={submit} loading={busy} disabled={!email || !password} />
        </Card>
        <Link href="/register" style={{ color: c.primary, textAlign: 'center', marginTop: space.md }}>
          {t('noAccount')}
        </Link>
      </View>
    </Screen>
  );
}
