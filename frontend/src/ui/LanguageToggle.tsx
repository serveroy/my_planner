import { Pressable, View } from 'react-native';

import type { Lang } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';

import { AppText } from './index';
import { radius, useColors } from './theme';

/** Compact two-option segmented control: English / עברית. */
export function LanguageToggle({ onChange }: { onChange?: (lang: Lang) => void }) {
  const { lang, setLang } = useI18n();
  const c = useColors();
  return (
    <View style={{ flexDirection: 'row', backgroundColor: c.fill, borderRadius: radius.pill, padding: 3, alignSelf: 'flex-start' }}>
      {(['en', 'he'] as const).map((l) => (
        <Pressable
          key={l}
          onPress={() => {
            setLang(l);
            onChange?.(l);
          }}
          style={{ paddingVertical: 4, paddingHorizontal: 12, borderRadius: radius.pill, backgroundColor: lang === l ? c.surface : 'transparent' }}>
          <AppText size={13} weight={lang === l ? '500' : '400'} style={{ color: lang === l ? c.text : c.muted }}>
            {l === 'en' ? 'English' : 'עברית'}
          </AppText>
        </Pressable>
      ))}
    </View>
  );
}
