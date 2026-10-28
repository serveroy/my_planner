import { Link } from 'expo-router';
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { useI18n } from '@/i18n/I18nContext';
import { AppText, Card, Icon, Screen } from '@/ui';
import { LanguageToggle } from '@/ui/LanguageToggle';
import { radius, space, useColors } from '@/ui/theme';

export function AuthShell({ title, children, footer, footerHref }: { title: string; children: ReactNode; footer: string; footerHref: '/login' | '/register' }) {
  const { t } = useI18n();
  const c = useColors();
  return (
    <Screen>
      <View style={{ alignItems: 'flex-end' }}>
        <LanguageToggle />
      </View>
      <View style={{ flex: 1, justifyContent: 'center', paddingVertical: space.xl }}>
        <View style={{ width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.primary, alignItems: 'center', justifyContent: 'center', marginBottom: space.md }}>
          <Icon name="flag" size={22} color={c.onPrimary} />
        </View>
        <AppText size={26} weight="700">{t('appName')}</AppText>
        <AppText muted style={{ marginTop: 2, marginBottom: space.xl }}>{t('tagline')}</AppText>
        <AppText size={17} weight="600" style={{ marginBottom: space.sm }}>{title}</AppText>
        <Card style={{ paddingVertical: space.lg }}>{children}</Card>
        <Link href={footerHref} style={{ color: c.primary, textAlign: 'center', marginTop: space.sm, fontSize: 14 }}>
          {footer}
        </Link>
      </View>
    </Screen>
  );
}
