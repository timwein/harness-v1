# Frontend Design Rubric

A comprehensive rubric for evaluating modern web and mobile app UI designs in 2025-2026. Based on research from Awwwards, Dribbble, Mobbin, and current design system trends from Apple, Google, and leading design agencies.

---

## Anti-Patterns: What to Avoid

Before the rubric, critical anti-patterns that immediately signal poor or outdated design:

### Color Anti-Patterns
❌ **Default AI purple** (`#8B5CF6`, `#7C3AED`, `#6366F1`) — The "Claude purple" or "AI assistant" purple is overused and signals low-effort design
❌ **Saturated rainbow gradients** — The 2019-2021 gradient trend is dated
❌ **Pure black (`#000000`) on pure white (`#FFFFFF`)** — Too harsh; use off-blacks and warm whites
❌ **Neon accents without purpose** — Neon works only as micro-accents, not primary colors
❌ **Blue-purple startup gradient** — The "SaaS hero gradient" is exhausted

### Layout Anti-Patterns
❌ **Centered everything** — Breaks visual hierarchy; use intentional alignment
❌ **Inconsistent spacing** — Random 13px, 17px gaps instead of 8px grid multiples
❌ **Cards floating in space** — No clear grouping or relationship
❌ **Wall of text** — No visual breaks or scannable hierarchy
❌ **Tiny touch targets** — Buttons smaller than 44px/48px

### Typography Anti-Patterns
❌ **More than 2 font families** — Creates visual chaos
❌ **Thin/light weights on mobile** — Poor readability on small screens
❌ **All caps for body text** — Hard to read, aggressive tone
❌ **Insufficient contrast** — Below 4.5:1 for body text, 3:1 for large text

---

## Template: Modern Frontend Design (Web & Mobile)

```yaml
rubric:
  id: "frontend_design_2026"
  version: "1.0"
  task_pattern: "design|UI|frontend|app|component|landing page|dashboard"
  
  criteria:
    # ===================
    # COLOR SYSTEM (Weight: Critical)
    # ===================
    - id: color_001
      weight: 3
      category: visual_design
      description: "Color palette is intentional, modern, and avoids AI clichés"
      pass_condition: |
        - NOT using default purple (#8B5CF6, #7C3AED, #6366F1, or similar)
        - Primary color is distinctive and purposeful
        - Palette follows 60-30-10 rule (dominant-secondary-accent)
        - Colors have semantic meaning (success=green, error=red, warning=amber)
        - Maximum 5-6 colors in active palette (excluding grays)
      
    - id: color_002
      weight: 3
      category: accessibility
      description: "Color contrast meets WCAG 2.1 AA standards"
      pass_condition: |
        - Body text: minimum 4.5:1 contrast ratio
        - Large text (18px+ or 14px bold): minimum 3:1 ratio
        - Interactive elements clearly distinguishable
        - Information not conveyed by color alone
        - Works in both light and dark modes (if applicable)
      
    - id: color_003
      weight: 2
      category: visual_design
      description: "Uses modern color trends appropriately"
      pass_condition: |
        - Warm neutrals over stark whites (Cloud Dancer #F0EEE9, not #FFFFFF)
        - Off-blacks (#1A1A1A, #0F0F0F) instead of pure black
        - Earthy tones, muted pastels, or sophisticated darks
        - Gradients are subtle/ambient, not rainbow
        - Metallics/glassmorphism used sparingly if at all
    
    # ===================
    # TYPOGRAPHY (Weight: Critical)
    # ===================
    - id: type_001
      weight: 3
      category: typography
      description: "Typography hierarchy is clear and consistent"
      pass_condition: |
        - Clear distinction between H1, H2, H3, body, caption
        - Size ratio between levels is noticeable (typically 1.2-1.5x)
        - Weight variation used purposefully (not random)
        - Maximum 2 font families (ideally 1 with multiple weights)
        - Line height 1.4-1.6x for body text
      
    - id: type_002
      weight: 3
      category: typography
      description: "Font choices are modern and readable"
      pass_condition: |
        - Uses modern sans-serif for UI (Inter, SF Pro, DM Sans, Satoshi, Geist)
        - OR intentional serif choice for brand personality
        - Font renders well at all sizes (14px minimum for body)
        - Variable fonts preferred for performance
        - Supports required character sets (Latin extended minimum)
      
    - id: type_003
      weight: 2
      category: typography
      description: "Typography feels intentional and branded"
      pass_condition: |
        - Headlines make visual impact (bold weights, appropriate size)
        - Consistent letter-spacing (tighter for headlines, normal for body)
        - Text alignment is intentional (left for reading, center sparingly)
        - No orphans/widows in key copy
        - Monospace for code/data if applicable
    
    # ===================
    # SPACING & LAYOUT (Weight: Critical)
    # ===================
    - id: space_001
      weight: 3
      category: layout
      description: "Spacing follows 8px grid system consistently"
      pass_condition: |
        - All spacing values are multiples of 8 (8, 16, 24, 32, 40, 48...)
        - 4px used only for micro-adjustments (icon-text gaps)
        - No arbitrary values (13px, 17px, 22px)
        - Consistent spacing scale applied throughout
        - Internal padding ≤ external margins (grouping principle)
      
    - id: space_002
      weight: 3
      category: layout
      description: "Visual hierarchy through spacing"
      pass_condition: |
        - Related elements grouped closer (8-16px)
        - Unrelated elements have clear separation (24-48px)
        - Sections have generous breathing room (48-96px)
        - White space used intentionally, not just "filling gaps"
        - Gestalt principles applied (proximity, similarity)
      
    - id: space_003
      weight: 2
      category: layout
      description: "Layout adapts to content and context"
      pass_condition: |
        - Bento/asymmetric grids where appropriate (2025 trend)
        - Cards/containers have consistent padding (16-24px)
        - Responsive breakpoints handle edge cases
        - Content doesn't feel cramped OR lost in space
        - Gutters consistent across similar components
    
    # ===================
    # COMPONENTS & PATTERNS (Weight: High)
    # ===================
    - id: comp_001
      weight: 2
      category: components
      description: "Interactive elements are clearly tappable/clickable"
      pass_condition: |
        - Touch targets minimum 44x44px (iOS) or 48x48dp (Android)
        - Buttons have clear affordance (filled, outlined, or elevated)
        - Hover/focus/active states defined
        - Disabled states visually distinct but not invisible
        - Links distinguishable from body text
      
    - id: comp_002
      weight: 2
      category: components
      description: "Navigation is intuitive and consistent"
      pass_condition: |
        - Bottom navigation for mobile primary actions (max 5 items)
        - Current location clearly indicated
        - Back/close actions easily accessible
        - Gesture navigation supported where appropriate
        - Consistent navigation patterns across screens
      
    - id: comp_003
      weight: 2
      category: components
      description: "Forms and inputs are user-friendly"
      pass_condition: |
        - Input fields have visible boundaries
        - Labels are visible (not just placeholders)
        - Error states are clear with helpful messages
        - Focus states are obvious
        - Appropriate keyboard types on mobile
    
    # ===================
    # VISUAL POLISH (Weight: Standard)
    # ===================
    - id: polish_001
      weight: 1
      category: visual_design
      description: "Consistent visual language throughout"
      pass_condition: |
        - Border radius consistent (all sharp, all rounded, or system)
        - Shadow depth consistent (elevation system)
        - Icon style unified (outline vs filled, stroke weight)
        - Illustration style cohesive if used
        - No mixed visual metaphors
      
    - id: polish_002
      weight: 1
      category: visual_design
      description: "Micro-interactions and feedback present"
      pass_condition: |
        - Loading states for async operations
        - Success/error feedback on actions
        - Subtle hover animations (if desktop)
        - Transitions are smooth (200-300ms)
        - No jarring state changes
      
    - id: polish_003
      weight: 1
      category: visual_design
      description: "Dark mode support (if applicable)"
      pass_condition: |
        - Not just inverted colors
        - Backgrounds use dark grays, not pure black
        - Reduced saturation on colors
        - Shadows become glows or disappear
        - Images/illustrations adapt or remain readable
    
    # ===================
    # ACCESSIBILITY (Weight: High)
    # ===================
    - id: a11y_001
      weight: 2
      category: accessibility
      description: "Screen reader compatibility"
      pass_condition: |
        - Semantic HTML structure (headings, landmarks, lists)
        - Alt text for meaningful images
        - ARIA labels for interactive elements
        - Focus order is logical
        - Skip links for navigation-heavy pages
      
    - id: a11y_002
      weight: 2
      category: accessibility
      description: "Keyboard and motor accessibility"
      pass_condition: |
        - All interactive elements keyboard accessible
        - Visible focus indicators
        - No keyboard traps
        - Click targets have adequate spacing
        - No time-limited interactions without override

  thresholds:
    pass_score: 0.85
    critical_required: true  # All weight=3 must pass
```

---

## Scoring Examples

### Example 1: Generic AI-Generated Dashboard

**Design Under Review:**
- Purple gradient header (#7C3AED → #6366F1)
- White background (#FFFFFF), black text (#000000)
- Random spacing (15px here, 20px there, 12px elsewhere)
- Font: System default sans-serif at various sizes
- Cards with 3px border radius, shadows inconsistent
- Purple accent buttons

**Scoring:**

| Criterion | Pass | Evidence |
|-----------|------|----------|
| color_001 | ✗ | Uses exact "AI purple" gradient. Not distinctive. |
| color_002 | ✓ | Black on white exceeds contrast minimums |
| color_003 | ✗ | Pure white/black, dated purple gradient |
| type_001 | ✗ | No clear hierarchy, sizes seem arbitrary |
| type_002 | △ | System font is readable but not intentional |
| type_003 | ✗ | No brand personality, generic feel |
| space_001 | ✗ | 15px, 20px, 12px — not on 8px grid |
| space_002 | ✗ | Elements don't group logically |
| space_003 | ✗ | Feels cramped, inconsistent padding |
| comp_001 | ✓ | Buttons are tappable size |
| comp_002 | ✓ | Basic navigation present |
| comp_003 | △ | Forms functional but bland |
| polish_001 | ✗ | Inconsistent border radius, shadow depth |
| polish_002 | ✗ | No loading states, jarring transitions |
| polish_003 | N/A | No dark mode |
| a11y_001 | ✗ | Missing ARIA labels, poor structure |
| a11y_002 | △ | Keyboard works but focus states weak |

**Score: 4/37 (10.8%)** — Fails critical criteria

**Fix Priority:**
1. Replace purple with intentional brand color
2. Establish 8px spacing grid
3. Define typography scale
4. Add warm whites, off-blacks

---

### Example 2: Modern Finance App

**Design Under Review:**
- Primary: Deep teal (#0D6E6E) 
- Background: Warm white (#FAFAF9)
- Text: Off-black (#1C1917)
- Accent: Coral (#F97316) for CTAs
- Font: Inter, clear H1/H2/Body hierarchy
- 8px grid: 16px component padding, 24px between sections
- Glassmorphism cards with 16px radius
- Bottom navigation with 5 items

**Scoring:**

| Criterion | Pass | Evidence |
|-----------|------|----------|
| color_001 | ✓ | Teal is distinctive, coral accent follows 60-30-10 |
| color_002 | ✓ | #1C1917 on #FAFAF9 = 15.4:1 contrast |
| color_003 | ✓ | Warm neutrals, sophisticated palette |
| type_001 | ✓ | H1 32px/bold, H2 24px/semibold, Body 16px/regular |
| type_002 | ✓ | Inter is modern, readable at all sizes |
| type_003 | ✓ | Headlines impactful, consistent tracking |
| space_001 | ✓ | All values 8/16/24/32/48 |
| space_002 | ✓ | Related items grouped at 8px, sections at 48px |
| space_003 | ✓ | Bento layout for portfolio view, 16px card padding |
| comp_001 | ✓ | Buttons 48px height, clear states |
| comp_002 | ✓ | Bottom nav with active indicator |
| comp_003 | ✓ | Inputs have labels, clear error states |
| polish_001 | ✓ | 16px radius throughout, consistent elevation |
| polish_002 | ✓ | Skeleton loaders, smooth 200ms transitions |
| polish_003 | ✓ | Dark mode uses #0F0F0F bg, desaturated teal |
| a11y_001 | ✓ | Proper heading structure, ARIA labels |
| a11y_002 | ✓ | Full keyboard nav, visible focus rings |

**Score: 37/37 (100%)** — Passes all criteria

---

### Example 3: E-commerce Product Page (Partial Pass)

**Design Under Review:**
- Brand orange (#EA580C) primary
- Light gray background (#F5F5F5)  
- System font stack
- Spacing mostly 8px grid (some 10px gaps)
- Good product imagery
- Small "Add to Cart" button (36px)

**Scoring:**

| Criterion | Pass | Evidence |
|-----------|------|----------|
| color_001 | ✓ | Orange is brand-appropriate for retail, not purple |
| color_002 | ✓ | Meets contrast requirements |
| color_003 | △ | Gray is neutral but cold, not warm |
| type_001 | △ | Hierarchy exists but weak distinction |
| type_002 | ✗ | System font lacks brand personality |
| type_003 | ✗ | Generic, could be any e-commerce site |
| space_001 | ✗ | 10px gaps break 8px grid |
| space_002 | ✓ | Product info grouped logically |
| space_003 | ✓ | Good responsive layout |
| comp_001 | ✗ | "Add to Cart" only 36px — below 44px minimum |
| comp_002 | ✓ | Clear category navigation |
| comp_003 | ✓ | Size selector, quantity input well-designed |
| polish_001 | ✓ | Consistent 8px radius, shadows |
| polish_002 | △ | Has loading but transitions choppy |
| polish_003 | ✗ | No dark mode |
| a11y_001 | ✓ | Good alt text on product images |
| a11y_002 | △ | Focus states present but subtle |

**Score: 19/37 (51.4%)** — Below threshold, needs work

**Fix Priority:**
1. Increase "Add to Cart" button to 48px height
2. Fix 10px spacing to 8px grid
3. Add intentional typography (e.g., Plus Jakarta Sans)
4. Warm up the gray background

---

## Modern Color Palettes (2025-2026)

### Palette 1: Warm Neutral (SaaS, Finance, Enterprise)
```
Background:   #FAFAF8 (warm white)
Surface:      #FFFFFF
Text Primary: #171717
Text Secondary: #525252
Border:       #E5E5E5
Primary:      #0D6E6E (teal)
Accent:       #F59E0B (amber)
Success:      #22C55E
Error:        #EF4444
```

### Palette 2: Dark Mode Professional (Dashboards, Dev Tools)
```
Background:   #0A0A0A
Surface:      #171717
Elevated:     #262626
Text Primary: #FAFAFA
Text Secondary: #A3A3A3
Border:       #262626
Primary:      #3B82F6 (blue)
Accent:       #F472B6 (pink)
Success:      #34D399
Error:        #F87171
```

### Palette 3: Earthy Modern (Lifestyle, Wellness, Eco)
```
Background:   #F5F5F0 (stone)
Surface:      #FFFFFF
Text Primary: #1C1917
Text Secondary: #78716C
Border:       #D6D3D1
Primary:      #2D5A27 (forest)
Accent:       #B45309 (terra cotta)
Success:      #15803D
Error:        #DC2626
```

### Palette 4: Bold Contemporary (Creative, Media, Youth)
```
Background:   #FAFAFA
Surface:      #FFFFFF
Text Primary: #09090B
Text Secondary: #71717A
Border:       #E4E4E7
Primary:      #DC2626 (red)
Accent:       #FBBF24 (yellow)
Success:      #10B981
Error:        #F43F5E
```

---

## Typography Scale (8px Grid Aligned)

### Mobile Scale
```
H1:     32px / 40px line-height / Bold (700)
H2:     24px / 32px line-height / Semibold (600)
H3:     20px / 28px line-height / Semibold (600)
Body:   16px / 24px line-height / Regular (400)
Body-sm: 14px / 20px line-height / Regular (400)
Caption: 12px / 16px line-height / Regular (400)
```

### Desktop Scale (1.125 ratio)
```
H1:     48px / 56px line-height / Bold (700)
H2:     36px / 44px line-height / Semibold (600)
H3:     24px / 32px line-height / Semibold (600)
Body:   16px / 24px line-height / Regular (400)
Body-lg: 18px / 28px line-height / Regular (400)
Caption: 14px / 20px line-height / Regular (400)
```

---

## Spacing Scale (8px Base)

```
--space-1:  4px   (micro: icon-label gap)
--space-2:  8px   (tight: related items)
--space-3:  12px  (compact: form field gap)
--space-4:  16px  (default: component padding)
--space-5:  20px  (relaxed: card content)
--space-6:  24px  (comfortable: between groups)
--space-8:  32px  (section gap)
--space-10: 40px  (large section gap)
--space-12: 48px  (major section break)
--space-16: 64px  (page section)
--space-20: 80px  (hero spacing)
--space-24: 96px  (major page break)
```

---

## Recommended Fonts (2025-2026)

### System/Native
- **SF Pro** (iOS) — Apple's default, highly optimized
- **Roboto** (Android) — Google's default, versatile

### Modern Sans-Serif (Recommended)
- **Inter** — The gold standard for UI, free, variable
- **DM Sans** — Geometric, great at small sizes, free
- **Satoshi** — Modern, sharp, free
- **Geist** — Vercel's font, Swiss-inspired, free
- **Plus Jakarta Sans** — Friendly, contemporary, free
- **General Sans** — Elegant, extended characters, free

### Premium Options
- **Söhne** (Klim) — Premium, used by Stripe
- **Neue Haas Grotesk** — Classic, refined
- **Untitled Sans** — Neutral, professional

### Modern Serif (For Personality)
- **Fraunces** — Variable, expressive, free
- **Newsreader** — Editorial, readable, free
- **Playfair Display** — Elegant headlines only

---

## Quick Checklist (Pre-Submission)

**Color**
- [ ] No default purple (#8B5CF6, #7C3AED, #6366F1)
- [ ] Background is warm white or intentional dark
- [ ] Text uses off-black, not pure black
- [ ] Accent color is purposeful, not decorative
- [ ] Passes WCAG AA contrast (check with WebAIM)

**Typography**
- [ ] Only 1-2 font families
- [ ] Clear size hierarchy (H1 > H2 > H3 > Body)
- [ ] Line height 1.4-1.6x for body
- [ ] Minimum 14px for body text

**Spacing**
- [ ] All values on 8px grid (8, 16, 24, 32...)
- [ ] Related items grouped (smaller gaps)
- [ ] Sections have breathing room (48px+)
- [ ] Internal padding ≤ external margins

**Components**
- [ ] Touch targets ≥ 44px
- [ ] Buttons have hover/active/disabled states
- [ ] Forms have visible labels and error states
- [ ] Navigation shows current location

**Polish**
- [ ] Consistent border radius
- [ ] Loading states present
- [ ] Smooth transitions (200-300ms)
- [ ] Dark mode considered (if applicable)
