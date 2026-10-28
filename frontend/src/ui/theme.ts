import { useColorScheme } from 'react-native';

// Warm "paper planner" palette: paper background, ink text, pine green for actions,
// terracotta for the coach and highlights.
const light = {
  bg: '#F6F2EA',
  surface: '#FFFDF8',
  fill: '#EFE9DF', // inputs, chips, secondary buttons
  text: '#24201B',
  muted: '#7B7368',
  faint: '#A79F93',
  border: '#E5DDD0',
  primary: '#2F5D50',
  onPrimary: '#FFFFFF',
  primarySoft: '#E2EBE5',
  accent: '#D9714F',
  accentSoft: '#F9E6DD',
  success: '#3E8A58',
  successSoft: '#E1EFE4',
  warning: '#B98222',
  warningSoft: '#F6ECD3',
  danger: '#B4473A',
  dangerSoft: '#F5E0DC',
  userBubble: '#2F5D50',
  onUserBubble: '#FFFFFF',
  botBubble: '#FFFDF8',
};

const dark: typeof light = {
  bg: '#191714',
  surface: '#23201C',
  fill: '#2D2924',
  text: '#EEE8DF',
  muted: '#A1988C',
  faint: '#776F65',
  border: '#36312B',
  primary: '#86B9A3',
  onPrimary: '#13211B',
  primarySoft: '#26352F',
  accent: '#EC9476',
  accentSoft: '#3A2620',
  success: '#7CC190',
  successSoft: '#1F3326',
  warning: '#E0B15A',
  warningSoft: '#3A2F1A',
  danger: '#E27E6F',
  dangerSoft: '#3B221E',
  userBubble: '#3A6B5D',
  onUserBubble: '#F4FAF7',
  botBubble: '#23201C',
};

export type Colors = typeof light;

export function useColors(): Colors {
  return useColorScheme() === 'dark' ? dark : light;
}

export const space = { xs: 4, sm: 6, md: 10, lg: 14, xl: 20 } as const;
export const radius = { sm: 6, md: 10, lg: 14, pill: 999 } as const;
export const MAX_WIDTH = 640;

// Rubik covers Hebrew and Latin; loaded in app/_layout.tsx.
export const fonts = {
  '400': 'Rubik_400Regular',
  '500': 'Rubik_500Medium',
  '600': 'Rubik_600SemiBold',
  '700': 'Rubik_700Bold',
} as const;
export type Weight = keyof typeof fonts;
