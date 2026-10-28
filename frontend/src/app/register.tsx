import { Link } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import { useI18n } from '@/i18n/I18nContext';
import { AppText, Button, Card, Field, Screen } from '@/ui';
import { LanguageToggle } from '@/ui/LanguageToggle';
import { space, useColors } from '@/ui/theme';

export default function Register() {
  const { register } = useAuth();
  const { t, lang } = useI18n();
  const c = useColors();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      await register(email.trim(), password, name.trim(), lang);
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
          {t('register')}
        </AppText>
        <Card>
          <Field label={t('displayName')} value={name} onChangeText={setName} autoComplete="name" />
          <Field label={t('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
          <Field label={t('password')} hint={t('passwordHint')} value={password} onChangeText={setPassword} secureTextEntry />
          {error ? <AppText style={{ color: c.danger, marginBottom: space.sm }}>{error}</AppText> : null}
          <Button title={t('register')} onPress={submit} loading={busy} disabled={!name || !email || password.length < 8} />
        </Card>
        <Link href="/login" style={{ color: c.primary, textAlign: 'center', marginTop: space.md }}>
          {t('haveAccount')}
        </Link>
      </View>
    </Screen>
  );
}
