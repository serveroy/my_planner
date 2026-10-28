import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  type TextProps,
  TextInput,
  type TextInputProps,
  View,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useI18n } from '@/i18n/I18nContext';

import { MAX_WIDTH, radius, space, useColors } from './theme';

export function AppText({ style, muted, size = 15, weight, ...rest }: TextProps & { muted?: boolean; size?: number; weight?: '400' | '500' | '600' | '700' }) {
  const c = useColors();
  return (
    <Text
      {...rest}
      style={[{ color: muted ? c.muted : c.text, fontSize: size, fontWeight: weight, textAlign: 'auto' }, style]}
    />
  );
}

export function Screen({ children, scroll = true, padded = true }: { children: ReactNode; scroll?: boolean; padded?: boolean }) {
  const c = useColors();
  const inner = <View style={[styles.inner, padded && { padding: space.lg }]}>{children}</View>;
  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      {scroll ? (
        <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
          {inner}
        </ScrollView>
      ) : (
        inner
      )}
    </SafeAreaView>
  );
}

export function Card({ children, style, tone }: { children: ReactNode; style?: ViewStyle; tone?: 'primary' | 'warning' | 'danger' | 'success' }) {
  const c = useColors();
  const bg = tone ? { primary: c.primarySoft, warning: c.warningSoft, danger: c.dangerSoft, success: c.successSoft }[tone] : c.card;
  return <View style={[styles.card, { backgroundColor: bg, borderColor: c.border }, style]}>{children}</View>;
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <View style={styles.sectionTitle}>
      <AppText size={17} weight="700">
        {children}
      </AppText>
      {right}
    </View>
  );
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled,
  loading,
  small,
  style,
}: {
  title: string;
  onPress?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  disabled?: boolean;
  loading?: boolean;
  small?: boolean;
  style?: ViewStyle;
}) {
  const c = useColors();
  const bg = { primary: c.primary, secondary: c.primarySoft, ghost: 'transparent', danger: c.dangerSoft }[variant];
  const fg = { primary: c.primaryText, secondary: c.primary, ghost: c.primary, danger: c.danger }[variant];
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        small && styles.buttonSmall,
        { backgroundColor: bg, opacity: disabled ? 0.45 : pressed ? 0.8 : 1 },
        style,
      ]}>
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <AppText style={{ color: fg }} weight="600" size={small ? 13 : 15}>
          {title}
        </AppText>
      )}
    </Pressable>
  );
}

export function Field({ label, hint, style, ...props }: TextInputProps & { label?: string; hint?: string }) {
  const c = useColors();
  return (
    <View style={{ marginBottom: space.md }}>
      {label ? (
        <AppText weight="600" size={14} style={{ marginBottom: space.xs }}>
          {label}
        </AppText>
      ) : null}
      <TextInput
        placeholderTextColor={c.muted}
        {...props}
        style={[
          styles.input,
          { borderColor: c.border, color: c.text, backgroundColor: c.card, textAlign: 'auto' },
          props.multiline && { minHeight: 80, textAlignVertical: 'top' },
          style,
        ]}
      />
      {hint ? (
        <AppText muted size={12} style={{ marginTop: 2 }}>
          {hint}
        </AppText>
      ) : null}
    </View>
  );
}

export function Chips<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T | T[];
  onChange: (v: T) => void;
  label?: string;
}) {
  const c = useColors();
  const selected = (v: T) => (Array.isArray(value) ? value.includes(v) : value === v);
  return (
    <View style={{ marginBottom: space.md }}>
      {label ? (
        <AppText weight="600" size={14} style={{ marginBottom: space.xs }}>
          {label}
        </AppText>
      ) : null}
      <View style={styles.chipRow}>
        {options.map((o) => (
          <Pressable
            key={String(o.value)}
            onPress={() => onChange(o.value)}
            style={[
              styles.chip,
              { borderColor: selected(o.value) ? c.primary : c.border, backgroundColor: selected(o.value) ? c.primarySoft : c.card },
            ]}>
            <AppText size={14} style={{ color: selected(o.value) ? c.primary : c.text }} weight={selected(o.value) ? '600' : '400'}>
              {o.label}
            </AppText>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

export function SwitchRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={[styles.row, { marginBottom: space.md }]}>
      <AppText style={{ flex: 1 }}>{label}</AppText>
      <Switch value={value} onValueChange={onChange} />
    </View>
  );
}

export function Badge({ text, tone = 'primary' }: { text: string; tone?: 'primary' | 'warning' | 'success' | 'danger' | 'muted' }) {
  const c = useColors();
  const map = {
    primary: [c.primarySoft, c.primary],
    warning: [c.warningSoft, c.warning],
    success: [c.successSoft, c.success],
    danger: [c.dangerSoft, c.danger],
    muted: [c.border, c.muted],
  } as const;
  const [bg, fg] = map[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <AppText size={12} weight="600" style={{ color: fg }}>
        {text}
      </AppText>
    </View>
  );
}

export function ProgressBar({ value }: { value: number }) {
  const c = useColors();
  return (
    <View style={[styles.bar, { backgroundColor: c.border }]}>
      <View style={{ width: `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%`, backgroundColor: c.success, height: '100%', borderRadius: radius.pill }} />
    </View>
  );
}

export function Loading() {
  const c = useColors();
  const { t } = useI18n();
  return (
    <View style={styles.center}>
      <ActivityIndicator color={c.primary} />
      <AppText muted style={{ marginTop: space.sm }}>
        {t('loading')}
      </AppText>
    </View>
  );
}

export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <View style={styles.center}>
      <AppText weight="600">{t('error')}</AppText>
      <AppText muted style={{ marginVertical: space.sm, textAlign: 'center' }}>
        {error instanceof Error ? error.message : String(error)}
      </AppText>
      {onRetry ? <Button title={t('retry')} onPress={onRetry} variant="secondary" /> : null}
    </View>
  );
}

export function Row({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.row, style]}>{children}</View>;
}

export const styles = StyleSheet.create({
  inner: { width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', flexGrow: 1 },
  card: { borderRadius: radius.lg, borderWidth: StyleSheet.hairlineWidth, padding: space.lg, marginBottom: space.md },
  sectionTitle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space.md, marginBottom: space.sm },
  button: { borderRadius: radius.md, paddingVertical: 12, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center' },
  buttonSmall: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: radius.sm },
  input: { borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  chip: { borderWidth: 1, borderRadius: radius.pill, paddingVertical: 7, paddingHorizontal: 13 },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  badge: { borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 3, alignSelf: 'flex-start' },
  bar: { height: 8, borderRadius: radius.pill, overflow: 'hidden', flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.xl },
});
