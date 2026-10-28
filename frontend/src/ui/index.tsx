import Feather from '@expo/vector-icons/Feather';
import { type ComponentProps, type ReactNode, useState } from 'react';
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

import { fonts, MAX_WIDTH, radius, space, useColors, type Weight } from './theme';

export type IconName = ComponentProps<typeof Feather>['name'];

export function Icon({ name, size = 18, color }: { name: IconName; size?: number; color?: string }) {
  const c = useColors();
  return <Feather name={name} size={size} color={color ?? c.text} />;
}

export function AppText({
  style,
  muted,
  size = 14,
  weight = '400',
  ...rest
}: TextProps & { muted?: boolean; size?: number; weight?: Weight }) {
  const c = useColors();
  return (
    <Text
      {...rest}
      style={[{ color: muted ? c.muted : c.text, fontSize: size, lineHeight: Math.round(size * 1.4), fontFamily: fonts[weight], textAlign: 'auto' }, style]}
    />
  );
}

/** `safeTop`: keep clear of the status bar / Dynamic Island on screens without a header. */
export function Screen({ children, scroll = true, safeTop }: { children: ReactNode; scroll?: boolean; safeTop?: boolean }) {
  const c = useColors();
  const inner = <View style={styles.inner}>{children}</View>;
  return (
    <SafeAreaView edges={safeTop ? ['top', 'bottom', 'left', 'right'] : ['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
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

export function Card({ children, style, tone, flush }: { children: ReactNode; style?: ViewStyle; tone?: 'primary' | 'accent' | 'warning' | 'danger'; flush?: boolean }) {
  const c = useColors();
  const bg = tone ? { primary: c.primarySoft, accent: c.accentSoft, warning: c.warningSoft, danger: c.dangerSoft }[tone] : c.surface;
  return (
    <View style={[styles.card, { backgroundColor: bg, borderColor: tone ? 'transparent' : c.border }, flush && { paddingVertical: 0 }, style]}>
      {children}
    </View>
  );
}

/** Small muted heading above a group. */
export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <View style={styles.sectionTitle}>
      <AppText muted size={12} weight="500" style={{ letterSpacing: 0.4, textTransform: 'uppercase' }}>
        {children}
      </AppText>
      {right}
    </View>
  );
}

/** A tappable header that shows or hides its content. */
export function Collapsible({ title, hint, children, initiallyOpen = false }: { title: string; hint?: string; children: ReactNode; initiallyOpen?: boolean }) {
  const c = useColors();
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <View style={{ marginBottom: space.md }}>
      <Pressable onPress={() => setOpen(!open)} style={({ pressed }) => [styles.row, { paddingVertical: space.sm, opacity: pressed ? 0.6 : 1 }]}>
        <View style={{ flex: 1 }}>
          <AppText weight="500">{title}</AppText>
          {hint && !open ? <AppText muted size={12}>{hint}</AppText> : null}
        </View>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} color={c.muted} />
      </Pressable>
      {open ? children : null}
    </View>
  );
}

export function Divider() {
  const c = useColors();
  return <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: c.border }} />;
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled,
  loading,
  small,
  icon,
  style,
}: {
  title?: string;
  onPress?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  disabled?: boolean;
  loading?: boolean;
  small?: boolean;
  icon?: IconName;
  style?: ViewStyle;
}) {
  const c = useColors();
  const bg = { primary: c.primary, secondary: c.fill, ghost: 'transparent', danger: c.dangerSoft }[variant];
  const fg = { primary: c.onPrimary, secondary: c.text, ghost: c.primary, danger: c.danger }[variant];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        small && styles.buttonSmall,
        { backgroundColor: bg, opacity: disabled ? 0.4 : pressed ? 0.75 : 1 },
        style,
      ]}>
      {loading ? (
        <ActivityIndicator color={fg} size="small" />
      ) : (
        <>
          {icon ? <Icon name={icon} size={small ? 14 : 16} color={fg} /> : null}
          {title ? (
            <AppText style={{ color: fg }} weight="500" size={small ? 13 : 14}>
              {title}
            </AppText>
          ) : null}
        </>
      )}
    </Pressable>
  );
}

export function IconButton({ name, onPress, label, color, badge }: { name: IconName; onPress: () => void; label: string; color?: string; badge?: boolean }) {
  const c = useColors();
  return (
    <Pressable onPress={onPress} accessibilityLabel={label} hitSlop={8} style={({ pressed }) => [styles.iconButton, { opacity: pressed ? 0.6 : 1 }]}>
      <Icon name={name} size={20} color={color ?? c.text} />
      {badge ? <View style={[styles.dot, { backgroundColor: c.accent, borderColor: c.surface }]} /> : null}
    </Pressable>
  );
}

export function Field({ label, hint, style, ...props }: TextInputProps & { label?: string; hint?: string }) {
  const c = useColors();
  return (
    <View style={{ marginBottom: space.md }}>
      {label ? (
        <AppText muted size={12} weight="500" style={{ marginBottom: 3 }}>
          {label}
        </AppText>
      ) : null}
      <TextInput
        placeholderTextColor={c.faint}
        {...props}
        style={[
          styles.input,
          { color: c.text, backgroundColor: c.fill, fontFamily: fonts['400'], textAlign: 'auto' },
          props.multiline && { minHeight: 64, textAlignVertical: 'top' },
          style,
        ]}
      />
      {hint ? (
        <AppText size={11} style={{ marginTop: 2, color: c.faint }}>
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
        <AppText muted size={12} weight="500" style={{ marginBottom: 4 }}>
          {label}
        </AppText>
      ) : null}
      <View style={styles.chipRow}>
        {options.map((o) => {
          const on = selected(o.value);
          return (
            <Pressable
              key={String(o.value)}
              onPress={() => onChange(o.value)}
              style={({ pressed }) => [styles.chip, { backgroundColor: on ? c.primary : c.fill, opacity: pressed ? 0.75 : 1 }]}>
              <AppText size={13} weight={on ? '500' : '400'} style={{ color: on ? c.onPrimary : c.text }}>
                {o.label}
              </AppText>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function SwitchRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  const c = useColors();
  return (
    <View style={[styles.row, { marginBottom: space.md, justifyContent: 'space-between' }]}>
      <AppText style={{ flex: 1 }}>{label}</AppText>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: c.primary, false: c.border }} thumbColor={c.surface} />
    </View>
  );
}

export function Badge({ text, tone = 'primary' }: { text: string; tone?: 'primary' | 'accent' | 'warning' | 'success' | 'danger' | 'muted' }) {
  const c = useColors();
  const map = {
    primary: [c.primarySoft, c.primary],
    accent: [c.accentSoft, c.accent],
    warning: [c.warningSoft, c.warning],
    success: [c.successSoft, c.success],
    danger: [c.dangerSoft, c.danger],
    muted: [c.fill, c.muted],
  } as const;
  const [bg, fg] = map[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <AppText size={11} weight="500" style={{ color: fg, lineHeight: 15 }}>
        {text}
      </AppText>
    </View>
  );
}

export function ProgressBar({ value, color }: { value: number; color?: string }) {
  const c = useColors();
  return (
    <View style={[styles.bar, { backgroundColor: c.fill }]}>
      <View style={{ width: `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%`, backgroundColor: color ?? c.primary, height: '100%', borderRadius: radius.pill }} />
    </View>
  );
}

export function Loading() {
  const c = useColors();
  const { t } = useI18n();
  return (
    <View style={[styles.center, { backgroundColor: c.bg }]}>
      <ActivityIndicator color={c.primary} />
      <AppText muted size={13} style={{ marginTop: space.sm }}>
        {t('loading')}
      </AppText>
    </View>
  );
}

export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const c = useColors();
  return (
    <View style={[styles.center, { backgroundColor: c.bg }]}>
      <Icon name="cloud-off" size={28} color={c.muted} />
      <AppText weight="500" style={{ marginTop: space.sm }}>{t('error')}</AppText>
      <AppText muted size={13} style={{ marginVertical: space.sm, textAlign: 'center' }}>
        {error instanceof Error ? error.message : String(error)}
      </AppText>
      {onRetry ? <Button title={t('retry')} onPress={onRetry} variant="secondary" small /> : null}
    </View>
  );
}

export function Row({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.row, style]}>{children}</View>;
}

export const styles = StyleSheet.create({
  inner: { width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', flexGrow: 1, padding: space.lg, paddingBottom: space.xl },
  card: { borderRadius: radius.lg, borderWidth: StyleSheet.hairlineWidth, paddingHorizontal: space.lg, paddingVertical: space.md, marginBottom: space.md },
  sectionTitle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space.sm, marginBottom: space.sm, minHeight: 22 },
  button: { flexDirection: 'row', gap: 6, borderRadius: radius.md, paddingVertical: 10, paddingHorizontal: 16, alignItems: 'center', justifyContent: 'center' },
  buttonSmall: { paddingVertical: 6, paddingHorizontal: 11, borderRadius: radius.sm },
  iconButton: { padding: 6 },
  dot: { position: 'absolute', top: 4, right: 4, width: 9, height: 9, borderRadius: 5, borderWidth: 1.5 },
  input: { borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 9, fontSize: 14 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderRadius: radius.pill, paddingVertical: 5, paddingHorizontal: 11 },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  badge: { borderRadius: radius.pill, paddingHorizontal: 8, paddingVertical: 2, alignSelf: 'flex-start' },
  // flexGrow (not flex: 1) so the bar keeps its height inside column layouts.
  bar: { height: 6, borderRadius: radius.pill, overflow: 'hidden', flexGrow: 1, alignSelf: 'stretch' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.xl },
});
