import { COMPONENT_STATES } from '../contracts/gp05-v1'

export const GP05_CANVASES = {
  cluster: { width: 1920, height: 720 },
  hud: { width: 1280, height: 480 },
  center: { width: 1920, height: 1080 },
  passenger: { width: 1920, height: 1080 },
} as const

export const GP05_RADII = {
  small: 8,
  medium: 12,
  large: 16,
} as const

export const GP05_COMPONENT_STATES = COMPONENT_STATES

export const GP05_FONT_STACKS = {
  cjk: '"Noto Sans SC", "Barlow", "Segoe UI", sans-serif',
  latin: '"Bahnschrift", "Barlow", "Segoe UI", sans-serif',
  ui: '"Barlow", "Noto Sans SC", "Segoe UI", sans-serif',
} as const
