import { useColorScheme } from 'react-native';

const light = {
  bg: '#F6F7F9',
  card: '#FFFFFF',
  text: '#15181D',
  muted: '#5F6672',
  border: '#E3E6EB',
  primary: '#2F6FEB',
  primaryText: '#FFFFFF',
  primarySoft: '#E7EEFD',
  success: '#1F9D57',
  successSoft: '#E3F5EA',
  warning: '#B26A00',
  warningSoft: '#FFF3DC',
  danger: '#C93838',
  dangerSoft: '#FCE8E8',
  userBubble: '#2F6FEB',
  userBubbleText: '#FFFFFF',
  botBubble: '#FFFFFF',
};

const dark: typeof light = {
  bg: '#0F1115',
  card: '#191C22',
  text: '#ECEEF2',
  muted: '#9AA1AD',
  border: '#2A2F38',
  primary: '#6C9CFF',
  primaryText: '#0B0D11',
  primarySoft: '#1E2A44',
  success: '#4CC985',
  successSoft: '#163223',
  warning: '#F2B04A',
  warningSoft: '#3A2C12',
  danger: '#F07070',
  dangerSoft: '#3A1818',
  userBubble: '#3B6FE0',
  userBubbleText: '#FFFFFF',
  botBubble: '#191C22',
};

export type Colors = typeof light;

export function useColors(): Colors {
  return useColorScheme() === 'dark' ? dark : light;
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const;
export const radius = { sm: 8, md: 12, lg: 18, pill: 999 } as const;
export const MAX_WIDTH = 720;
