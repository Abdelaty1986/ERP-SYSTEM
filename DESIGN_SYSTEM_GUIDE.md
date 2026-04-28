# Design System Implementation Guide

## For Developers: Extending the Modern ERP UI

### 1. CSS Custom Properties Reference

All design values are centralized in CSS variables at the top of `static/style.css`:

```css
:root {
    /* Colors */
    --bg: #f3f5f7;                    /* Page background */
    --bg-soft: #f8fafb;               /* Soft backgrounds */
    --panel: #ffffff;                 /* Card/panel background */
    --panel-soft: #fafbfc;            /* Light panel variant */
    --ink: #2d3436;                   /* Primary text color */
    --muted: #6c757d;                 /* Secondary text color */
    --line: #e0e3e8;                  /* Border color */
    --line-strong: #d1d5db;           /* Strong border color */
    
    /* Special colors */
    --accent: #0061be;                /* Primary action color (blue) */
    --accent-soft: #e3f2fd;           /* Light accent background */
    --danger: #dc3545;                /* Delete/error color (red) */
    --warning: #ffc107;               /* Warning color (yellow) */
    --success: #28a745;               /* Success color (green) */
    --info: #17a2b8;                  /* Info color (cyan) */
    
    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.06);
    --shadow-lg: 0 4px 6px rgba(0,0,0,0.08), 0 12px 24px rgba(0,0,0,0.1);
    --shadow-xl: 0 8px 16px rgba(0,0,0,0.12), 0 20px 32px rgba(0,0,0,0.08);
}
```

**To change the theme:** Modify these variables only. The entire application will update automatically.

---

### 2. Adding New Components

#### New Badge Style

```css
.badge-custom {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    background: var(--bg-soft);
    color: var(--muted);
}

.badge-custom.success {
    background: #d4edda;
    color: #155724;
}
```

#### New Status Indicator

```css
.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--muted);
    margin-right: 8px;
}

.status-dot.active {
    background: var(--success);
}

.status-dot.inactive {
    background: var(--danger);
}
```

#### New Divider

```css
.divider {
    height: 1px;
    background: var(--line);
    margin: 20px 0;
}

.divider.strong {
    background: var(--line-strong);
}
```

---

### 3. Extending Button Styles

#### New Button Variant - Success

```css
.btn-success {
    background: var(--success);
    border-color: var(--success);
    color: #fff;
}

.btn-success:hover {
    background: #218838;
    border-color: #218838;
}
```

#### New Button Variant - Ghost

```css
.btn-ghost {
    background: transparent;
    color: var(--ink);
    border: 1px solid transparent;
}

.btn-ghost:hover {
    background: var(--bg-soft);
    border-color: var(--line);
}
```

---

### 4. Extending Form Validation

```css
/* Invalid state */
.form-control.is-invalid {
    border-color: var(--danger);
    box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.1);
}

.form-control.is-invalid:focus {
    border-color: var(--danger);
    box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.25);
}

/* Valid state */
.form-control.is-valid {
    border-color: var(--success);
    box-shadow: 0 0 0 3px rgba(40, 167, 69, 0.1);
}

.form-control.is-valid:focus {
    border-color: var(--success);
    box-shadow: 0 0 0 3px rgba(40, 167, 69, 0.25);
}

/* Feedback text */
.form-feedback {
    display: block;
    margin-top: 4px;
    font-size: 12px;
    font-weight: 500;
}

.form-feedback.error {
    color: var(--danger);
}

.form-feedback.success {
    color: var(--success);
}
```

---

### 5. Creating Cards with Variants

#### Card with Icon Header

```css
.card-with-icon .card-header {
    display: flex;
    align-items: center;
    gap: 12px;
}

.card-with-icon .card-header i {
    font-size: 20px;
    color: var(--accent);
}

.card-with-icon .card-header h5 {
    flex: 1;
    margin: 0;
}
```

#### Card with Top Border

```css
.card-bordered-top {
    border-top: 4px solid var(--accent);
    border-radius: 0 0 12px 12px;
}

.card-bordered-top.danger {
    border-top-color: var(--danger);
}

.card-bordered-top.success {
    border-top-color: var(--success);
}
```

---

### 6. Responsive Patterns

#### Responsive Grid

```css
.responsive-grid {
    display: grid;
    gap: 20px;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}

@media (max-width: 768px) {
    .responsive-grid {
        grid-template-columns: 1fr;
    }
}
```

#### Responsive Typography

```css
.responsive-heading {
    font-size: 28px;
    font-weight: 700;
}

@media (max-width: 768px) {
    .responsive-heading {
        font-size: 22px;
    }
}

@media (max-width: 480px) {
    .responsive-heading {
        font-size: 18px;
    }
}
```

---

### 7. Animation Patterns

#### Fade In Animation

```css
@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

.fade-in {
    animation: fadeIn 0.3s ease;
}
```

#### Scale Animation (for popups)

```css
@keyframes scaleIn {
    from {
        opacity: 0;
        transform: scale(0.95);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

.scale-in {
    animation: scaleIn 0.2s ease;
}
```

---

### 8. Theming Examples

#### Dark Mode Variables

```css
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #1a1a1a;
        --bg-soft: #2d2d2d;
        --panel: #2a2a2a;
        --panel-soft: #333333;
        --ink: #ffffff;
        --muted: #b0b0b0;
        --line: #444444;
        --line-strong: #555555;
    }
}
```

#### Seasonal Theme

```css
.theme-spring {
    --accent: #22c55e;
    --accent-soft: #dcfce7;
}

.theme-summer {
    --accent: #f59e0b;
    --accent-soft: #fef3c7;
}

.theme-autumn {
    --accent: #ef4444;
    --accent-soft: #fee2e2;
}

.theme-winter {
    --accent: #06b6d4;
    --accent-soft: #cffafe;
}
```

---

### 9. Best Practices

#### DO ✅

```css
/* Use CSS variables */
background: var(--bg-soft);
color: var(--accent);
box-shadow: var(--shadow);

/* Use semantic class names */
.btn-primary
.card-header
.empty-state

/* Group related properties */
.component {
    /* Layout */
    display: flex;
    gap: 12px;
    
    /* Box model */
    padding: 16px;
    border-radius: 8px;
    
    /* Visual */
    background: var(--panel);
    border: 1px solid var(--line);
    
    /* Interaction */
    transition: all 0.2s ease;
    cursor: pointer;
}
```

#### DON'T ❌

```css
/* Don't hardcode colors */
background: #3498db;  /* Use var(--accent) instead */

/* Don't use generic names */
.blue-box      /* Use .card instead */
.main-stuff    /* Use .card-header instead */

/* Don't mix units */
.button {
    padding: 0.5rem 10px;  /* Use consistent units */
}

/* Don't use !important */
color: var(--ink) !important;  /* Restructure specificity instead */
```

---

### 10. Maintenance Checklist

- [ ] All new components use CSS variables
- [ ] Colors consistent with design system
- [ ] Typography follows hierarchy (13px, 14px, 16px, 18px, 26px)
- [ ] Spacing follows grid (4px, 8px, 12px, 16px, 20px, 24px)
- [ ] Shadows use defined shadow levels
- [ ] Transitions are smooth (0.15s - 0.3s)
- [ ] Components are responsive-first
- [ ] Focus states are visible (keyboard accessible)
- [ ] Dark mode compatible (if applicable)
- [ ] No hardcoded colors
- [ ] No duplicate styles
- [ ] Performance optimized (no excessive nesting)

---

### 11. Common Tasks

#### Change Primary Color Globally

1. Open `static/style.css`
2. Find `:root` section
3. Change `--accent: #0061be;` to desired color
4. Change `--accent-soft: #e3f2fd;` to light variant

That's it! All components will update automatically.

#### Add New Color Status

```css
/* In :root section */
--info-light: #d1ecf1;
--info-dark: #0c5460;

/* In component CSS */
.badge-info {
    background: var(--info-light);
    color: var(--info-dark);
}
```

#### Create Utility Classes

```css
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-muted { color: var(--muted); }
.text-success { color: var(--success); }

.gap-small { gap: 8px; }
.gap-medium { gap: 16px; }
.gap-large { gap: 24px; }

.shadow-hover:hover { box-shadow: var(--shadow-lg); }
.elevate-hover:hover { transform: translateY(-2px); }
```

---

### 12. Testing Checklist

- [ ] Render on Chrome/Firefox/Safari
- [ ] Check on mobile devices (iOS/Android)
- [ ] Test dark mode (if applicable)
- [ ] Verify keyboard navigation (Tab/Shift+Tab)
- [ ] Check focus states visible
- [ ] Test print preview
- [ ] Validate contrast ratios (WCAG AA minimum)
- [ ] Check animation performance
- [ ] Verify all hover/active states
- [ ] Test form validation states

---

## Quick Reference

### Font Sizes
- `12px` - Small text, labels
- `13px` - Body text
- `14px` - Regular
- `16px` - Prominent
- `18px` - Section title
- `26px` - Page title

### Spacing
- `4px` - Tiny gap
- `8px` - Small gap
- `12px` - Medium gap
- `16px` - Standard gap
- `20px` - Large gap
- `24px` - Extra large gap

### Border Radius
- `8px` - Inputs, small components
- `12px` - Cards, panels
- `20px` - Badges, pills
- `50%` - Circles

### Transition Times
- `0.15s` - Quick interactions
- `0.2s` - Standard
- `0.3s` - Noticeable animations

---

## Support & Questions

For questions about the design system:
1. Check CSS variables in `:root`
2. Search for similar components
3. Follow existing patterns
4. Refer to this guide
5. Keep consistency with existing code

---

**Last Updated:** April 20, 2026
**Design System Version:** 2.0
**Framework:** Pure CSS (no dependencies)
