---
name: NeuroFlow
colors:
  surface: '#fbf8fa'
  surface-dim: '#dcd9db'
  surface-bright: '#fbf8fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3f4'
  surface-container: '#f0edef'
  surface-container-high: '#eae7e9'
  surface-container-highest: '#e4e2e3'
  on-surface: '#1b1b1d'
  on-surface-variant: '#45474c'
  inverse-surface: '#303032'
  inverse-on-surface: '#f3f0f2'
  outline: '#75777d'
  outline-variant: '#c5c6cd'
  surface-tint: '#545f73'
  primary: '#091426'
  on-primary: '#ffffff'
  primary-container: '#1e293b'
  on-primary-container: '#8590a6'
  inverse-primary: '#bcc7de'
  secondary: '#006b5f'
  on-secondary: '#ffffff'
  secondary-container: '#62fae3'
  on-secondary-container: '#007165'
  tertiary: '#201100'
  on-tertiary: '#ffffff'
  tertiary-container: '#3c2300'
  on-tertiary-container: '#c88000'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e3fb'
  primary-fixed-dim: '#bcc7de'
  on-primary-fixed: '#111c2d'
  on-primary-fixed-variant: '#3c475a'
  secondary-fixed: '#62fae3'
  secondary-fixed-dim: '#3cddc7'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005047'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#fbf8fa'
  on-background: '#1b1b1d'
  surface-variant: '#e4e2e3'
typography:
  headline-lg:
    fontFamily: Atkinson Hyperlegible Next
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Atkinson Hyperlegible Next
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Atkinson Hyperlegible Next
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.05em
  stats-display:
    fontFamily: Atkinson Hyperlegible Next
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 48px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  touch-target-min: 48px
  gutter: 24px
  margin-mobile: 20px
  margin-desktop: 64px
  stack-gap: 16px
---

## Brand & Style

This design system is engineered for patients managing Parkinson's disease, prioritizing cognitive ease, physical accessibility, and emotional stability. The brand personality is **Clinical yet Compassionate**, bridging the gap between medical-grade data and human wellness. 

The aesthetic follows a **Refined Minimalism** approach. By utilizing generous whitespace and a restricted visual vocabulary, the interface minimizes cognitive load and "visual noise" that can be overstimulating. The emotional response is one of "Guided Calm"—users should feel in control, safe, and supported. Every interaction is designed to accommodate tremors or limited fine motor skills through high-contrast affordances and oversized interactive zones.

## Colors

The palette is rooted in medical reliability and physiological signaling:
- **Primary (Deep Slate Blue):** Used for core navigation, text, and structural elements to establish authority and trust.
- **Success/Calm (Soft Teal):** Represents healthy biofeedback ranges and "rest" states. It provides a soothing counterpoint to the darker primary tones.
- **Warning (Warm Amber):** Used for mild stress detection or notifications requiring attention without causing panic.
- **Alert (Coral):** Reserved for high-stress indicators or critical biometric alerts, ensuring immediate visibility through high chromatic contrast against the light background.

The background uses a "Cool Gray" wash (#F8FAFC) rather than pure white to reduce glare, which can be taxing for users with light sensitivity.

## Typography

Accessibility is the primary driver for typography. We utilize **Atkinson Hyperlegible Next** for headlines and data displays; its character differentiation is specifically designed to increase legibility for users with visual impairments. **Inter** is used for body copy to maintain a clean, systematic feel.

**Key Rules:**
- **Minimum Size:** No functional text should fall below 14px.
- **Contrast:** Maintain a minimum 4.5:1 ratio for all body text.
- **Line Height:** Generous leading (1.5x for body) ensures that lines of text are easily trackable even if the device is moving slightly due to tremors.

## Layout & Spacing

The layout utilizes a **Fluid Grid** with exaggerated safe areas. To accommodate Parkinson's-related motor challenges, the spacing system prioritizes "Fitts's Law": larger targets are easier to hit.

- **Touch Targets:** A strict minimum of 48x48px for all interactive elements, with a preferred 56px height for primary actions.
- **Negative Space:** Use 24px gutters to prevent "fat-finger" errors where a user might accidentally trigger a neighboring button.
- **Alignment:** Consistent left-alignment is used across all views to provide a predictable anchor point for the eye.

## Elevation & Depth

This design system uses **Tonal Layers** combined with **Ambient Shadows** to define hierarchy. 

- **Level 0 (Background):** The base light gray surface.
- **Level 1 (Cards):** White surfaces with a soft, diffused shadow (12px blur, 5% opacity, Slate Blue tint). These house the primary content.
- **Level 2 (Active Elements):** Elements currently being interacted with or "Global Action Buttons" use a slightly deeper shadow to appear physically "lifted" toward the user, providing a clear tactile metaphor.

Avoid complex gradients or heavy textures; depth should feel airy and light.

## Shapes

The shape language is **Soft and Approachable**. A standard 0.5rem (8px) corner radius is applied to most containers to eliminate the perceived "sharpness" of medical software. 

- **Primary Buttons:** Use `rounded-xl` (1.5rem) to create a friendly, pill-like appearance that invites interaction.
- **Selection Indicators:** Use `rounded-lg` (1rem) for checkboxes and radio containers to make them feel like distinct, touchable "tiles" rather than small abstract icons.

## Components

### Buttons
Primary buttons are full-width on mobile to maximize hit area. They use the Deep Slate Blue background with White text. Secondary buttons use a Soft Teal outline (2px) to denote "calm" or "positive" progression.

### Cards
Cards are the primary container for biofeedback data (e.g., tremor frequency, heart rate). They must feature a "High Contrast" header and at least 16px of internal padding to ensure content does not feel cramped.

### Input Fields
Inputs must have a persistent 2px border in a neutral Slate. When focused, the border thickens and changes to Soft Teal. Labels are always visible (never placeholder-only) to assist with short-term memory and cognitive focus.

### Haptic Feedback Progress Bars
Unique to this design system, progress bars and "Live Biofeedback" rings should use the Soft Teal-to-Coral color spectrum. They should be accompanied by clear numerical data in the `stats-display` type style for dual-encoding (color + value).

### Lists
List items feature a minimum height of 64px and include a chevron icon to signal "tappability," providing clear affordance for users with reduced tactile sensitivity.