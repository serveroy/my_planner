import { useState } from 'react';

import { API_URL } from '@/api/client';
import { useDevTick, useUpdateMe } from '@/api/hooks';
import { useAuth } from '@/auth/AuthContext';
import { useI18n } from '@/i18n/I18nContext';
import { localTimeISO } from '@/lib/text';
import { AppText, Button, Card, Field, Screen, SectionTitle } from '@/ui';
import { LanguageToggle } from '@/ui/LanguageToggle';
import { space, useColors } from '@/ui/theme';

export default function Settings() {
  const { user, setUser, logout } = useAuth();
  const { t, lang, needsRestart } = useI18n();
  const c = useColors();
  const updateMe = useUpdateMe();
  const tick = useDevTick();
  const [name, setName] = useState(user?.display_name ?? '');
  const [tz, setTz] = useState(user?.timezone ?? '');

  const save = () =>
    updateMe.mutate({ display_name: name.trim(), timezone: tz.trim(), language: lang }, { onSuccess: setUser });

  return (
    <Screen>
      <SectionTitle>{t('profile')}</SectionTitle>
      <Card>
        <AppText muted style={{ marginBottom: space.md }}>{user?.email}</AppText>
        <Field label={t('displayName')} value={name} onChangeText={setName} />
        <Field label={t('timezone')} value={tz} onChangeText={setTz} autoCapitalize="none" />
        <AppText weight="600" size={14} style={{ marginBottom: space.xs }}>{t('appLanguage')}</AppText>
        <LanguageToggle />
        {needsRestart ? <AppText style={{ color: c.warning, marginBottom: space.sm }}>{t('restartForRtl')}</AppText> : null}
        <Button title={updateMe.isSuccess ? t('saved') : t('save')} onPress={save} loading={updateMe.isPending} />
        {updateMe.error ? <AppText style={{ color: c.danger, marginTop: space.sm }}>{updateMe.error.message}</AppText> : null}
      </Card>

      <SectionTitle>{t('developer')}</SectionTitle>
      <Card>
        <AppText muted size={13} style={{ marginBottom: space.md, writingDirection: 'ltr' }}>
          {t('serverUrl', { url: API_URL })}
        </AppText>
        <Button title={t('devTick')} variant="secondary" onPress={() => tick.mutate(undefined)} loading={tick.isPending} style={{ marginBottom: space.sm }} />
        <Button title={t('devEvening')} variant="secondary" onPress={() => tick.mutate(localTimeISO(20, 30))} disabled={tick.isPending} style={{ marginBottom: space.sm }} />
        <Button title={t('devTomorrow')} variant="secondary" onPress={() => tick.mutate(localTimeISO(9, 0, 1))} disabled={tick.isPending} />
        {tick.data ? <AppText muted style={{ marginTop: space.sm }}>{t('devResult', { c: tick.data.checkins, r: tick.data.reviews })}</AppText> : null}
        {tick.error ? <AppText style={{ color: c.danger, marginTop: space.sm }}>{tick.error.message}</AppText> : null}
      </Card>

      <Button title={t('logout')} variant="danger" onPress={logout} style={{ marginTop: space.md, marginBottom: space.xl }} />
    </Screen>
  );
}
