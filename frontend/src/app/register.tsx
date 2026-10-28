import { useState } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { AuthShell } from '@/components/AuthShell';
import { useI18n } from '@/i18n/I18nContext';
import { AppText, Button, Field } from '@/ui';
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
    <AuthShell title={t('register')} footer={t('haveAccount')} footerHref="/login">
      <Field label={t('displayName')} value={name} onChangeText={setName} autoComplete="name" />
      <Field label={t('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label={t('password')} hint={t('passwordHint')} value={password} onChangeText={setPassword} secureTextEntry />
      {error ? <AppText size={13} style={{ color: c.danger, marginBottom: space.sm }}>{error}</AppText> : null}
      <Button title={t('register')} onPress={submit} loading={busy} disabled={!name || !email || password.length < 8} />
    </AuthShell>
  );
}
