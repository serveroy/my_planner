import type { ReactNode } from 'react';
import { StyleSheet, View, type ViewStyle } from 'react-native';

import { textDir } from '@/lib/text';
import { AppText } from '@/ui';
import { useColors } from '@/ui/theme';

/** Chat bubble: the user's on the trailing side in pine, the coach's on the leading side in paper. */
export function Bubble({ text, mine, tint, children, style }: { text: string; mine?: boolean; tint?: string; children?: ReactNode; style?: ViewStyle }) {
  const c = useColors();
  return (
    <View
      style={[
        {
          alignSelf: mine ? 'flex-end' : 'flex-start',
          maxWidth: '86%',
          backgroundColor: mine ? c.userBubble : (tint ?? c.botBubble),
          borderWidth: mine || tint ? 0 : StyleSheet.hairlineWidth,
          borderColor: c.border,
          borderRadius: 16,
          borderBottomEndRadius: mine ? 4 : 16,
          borderBottomStartRadius: mine ? 16 : 4,
          paddingVertical: 7,
          paddingHorizontal: 12,
          marginBottom: 6,
        },
        style,
      ]}>
      <AppText style={[{ color: mine ? c.onUserBubble : c.text }, textDir(text)]}>{text}</AppText>
      {children}
    </View>
  );
}
