import { useState } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { AuthShell } from '@/components/AuthShell';
import { useI18n } from '@/i18n/I18nContext';
import { AppText, Button, Field } from '@/ui';
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
    <AuthShell title={t('login')} footer={t('noAccount')} footerHref="/register">
      <Field label={t('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label={t('password')} value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={submit} />
      {error ? <AppText size={13} style={{ color: c.danger, marginBottom: space.sm }}>{error}</AppText> : null}
      <Button title={t('login')} onPress={submit} loading={busy} disabled={!email || !password} />
    </AuthShell>
  );
}
