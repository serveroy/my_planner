import { useState } from 'react';
import { View } from 'react-native';

import { API_URL } from '@/api/client';
import { useDevTick, useUpdateMe } from '@/api/hooks';
import { useAuth } from '@/auth/AuthContext';
import { useI18n } from '@/i18n/I18nContext';
import { localTimeISO } from '@/lib/text';
import { AppText, Button, Card, Field, Row, Screen, SectionTitle } from '@/ui';
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
      <Card style={{ paddingVertical: space.lg }}>
        <AppText muted size={13} style={{ marginBottom: space.md }}>{user?.email}</AppText>
        <Field label={t('displayName')} value={name} onChangeText={setName} />
        <Field label={t('timezone')} value={tz} onChangeText={setTz} autoCapitalize="none" />
        <AppText muted size={12} weight="500" style={{ marginBottom: 4 }}>{t('appLanguage')}</AppText>
        {/* Saved right away: the account language is applied again on every app start. */}
        <LanguageToggle onChange={(language) => updateMe.mutate({ language }, { onSuccess: setUser })} />
        {needsRestart ? <AppText size={12} style={{ color: c.warning, marginTop: space.sm }}>{t('restartForRtl')}</AppText> : null}
        <Button title={updateMe.isSuccess ? t('saved') : t('save')} icon={updateMe.isSuccess ? 'check' : undefined} onPress={save} loading={updateMe.isPending} style={{ marginTop: space.lg }} />
        {updateMe.error ? <AppText size={12} style={{ color: c.danger, marginTop: space.sm }}>{updateMe.error.message}</AppText> : null}
      </Card>

      <SectionTitle>{t('developer')}</SectionTitle>
      <Card>
        <AppText size={12} style={{ color: c.faint, marginBottom: space.sm, writingDirection: 'ltr' }}>
          {t('serverUrl', { url: API_URL })}
        </AppText>
        <Row style={{ flexWrap: 'wrap' }}>
          <Button title={t('devTick')} icon="play" small variant="secondary" onPress={() => tick.mutate(undefined)} loading={tick.isPending} />
          <Button title={t('devEvening')} icon="moon" small variant="secondary" onPress={() => tick.mutate(localTimeISO(20, 30))} disabled={tick.isPending} />
          <Button title={t('devTomorrow')} icon="sunrise" small variant="secondary" onPress={() => tick.mutate(localTimeISO(9, 0, 1))} disabled={tick.isPending} />
        </Row>
        {tick.data ? <AppText muted size={12} style={{ marginTop: space.sm }}>{t('devResult', { c: tick.data.checkins, r: tick.data.reviews })}</AppText> : null}
        {tick.error ? <AppText size={12} style={{ color: c.danger, marginTop: space.sm }}>{tick.error.message}</AppText> : null}
      </Card>

      <View style={{ marginTop: space.sm }}>
        <Button title={t('logout')} icon="log-out" variant="danger" onPress={logout} />
      </View>
    </Screen>
  );
}
