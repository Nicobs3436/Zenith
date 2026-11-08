export const zenith = {
  colors: {
    background: '#09090e',
    backgroundOuter: '#050508',
    foreground: '#f0f0f5',
    card: '#111118',
    secondary: '#1c1c26',
    // Ajustado para contraste WCAG AA (>= 4.5:1) tambien sobre `secondary`.
    muted: '#8a8aa6',
    border: 'rgba(255,255,255,0.07)',
    primary: '#c8f135',
    primarySoft: 'rgba(200,241,53,0.12)',
    primaryBorder: 'rgba(200,241,53,0.22)',
    primaryForeground: '#09090e',
    cyan: '#4eefc4',
    violet: '#7c6fff',
    amber: '#f1b535',
    danger: '#e84040',
    dangerSoft: 'rgba(232,64,64,0.12)',
    success: '#4eefc4',
  },
  font: {
    body: 'DMSans_400Regular',
    bodyMedium: 'DMSans_500Medium',
    bodyBold: 'DMSans_700Bold',
    display: 'BarlowCondensed_800ExtraBold',
    displayBold: 'BarlowCondensed_700Bold',
    mono: 'JetBrainsMono_500Medium',
  },
  radius: {
    sm: 10,
    md: 14,
    lg: 18,
    xl: 22,
    pill: 999,
  },
  spacing: {
    page: 20,
    bottomNav: 92,
  },
} as const;

export const routineAccents = ['#c8f135', '#4eefc4', '#7c6fff', '#f1b535', '#f14f35'] as const;
