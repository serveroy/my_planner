import { useI18n } from '@/i18n/I18nContext';

import { Chips } from './index';

export function LanguageToggle() {
  const { lang, setLang } = useI18n();
  return (
    <Chips
      options={[
        { value: 'en', label: 'English' },
        { value: 'he', label: 'עברית' },
      ]}
      value={lang}
      onChange={setLang}
    />
  );
}
