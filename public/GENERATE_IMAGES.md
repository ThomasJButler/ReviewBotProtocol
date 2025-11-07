# Generate Social Media Images

## Quick Manual Method (5 minutes)

Since automated generation has Chrome/Puppeteer compatibility issues on Mac Silicon, use this manual method:

### Method 1: Browser Screenshot (Recommended)

1. **Open the template**:

   ```bash
   open public/og-image-template.html
   ```

2. **For OG Image (1200x630)**:
   - Open Chrome DevTools (Cmd+Option+I)
   - Click "Toggle Device Toolbar" or press Cmd+Shift+M
   - Select "Responsive" mode
   - Set dimensions to **1200 x 630**
   - Take screenshot:
     - Chrome: Right-click > "Capture screenshot"
     - Or use Cmd+Shift+4 and manually select the area
   - Save as `public/og-image.png`

3. **For Twitter Card (1200x675)**:
   - In DevTools responsive mode
   - Change dimensions to **1200 x 675**
   - Take screenshot
   - Save as `public/twitter-card.png`

### Method 2: Online Tool

1. Visit https://www.screely.com/ or https://browserframe.com/
2. Upload `public/og-image-template.html`
3. Set dimensions to 1200x630
4. Download as PNG
5. Repeat for 1200x675 (Twitter)

### Method 3: VS Code Extension

1. Install "vscode-screenshot" extension
2. Open `public/og-image-template.html` in Live Server
3. Use extension to capture at exact dimensions

## Favicon Generation

### Quick Method

1. Visit https://realfavicongenerator.net
2. Upload `public/favicon.svg`
3. Generate all sizes
4. Download package
5. Extract to `public/` folder

### Manual Method with ImageMagick

```bash
# Install ImageMagick if not installed
brew install imagemagick

# Generate favicons from SVG
convert public/favicon.svg -resize 16x16 public/favicon-16x16.png
convert public/favicon.svg -resize 32x32 public/favicon-32x32.png
convert public/favicon.svg -resize 64x64 public/favicon-64x64.png

# Create .ico file (optional)
convert public/favicon-16x16.png public/favicon-32x32.png public/favicon.ico
```

## Verify Images

After generating, verify your images:

1. **OG Image**: https://www.opengraph.xyz/
2. **Twitter Card**: https://cards-dev.twitter.com/validator
3. **Favicon**: Check in browser dev tools

## Update Metadata

After creating images, update `app/layout.tsx`:

```typescript
export const metadata: Metadata = {
  // ... existing metadata
  openGraph: {
    images: ['/og-image.png'],
  },
  twitter: {
    images: ['/twitter-card.png'],
    card: 'summary_large_image',
  },
  icons: {
    icon: [
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon.svg', type: 'image/svg+xml' },
    ],
  },
}
```

## Troubleshooting

**Images look blurry?**

- Ensure you're capturing at exact pixel dimensions
- Don't resize after capture - take at native size

**Fonts not loading?**

- Open template in actual browser (not just file preview)
- Wait 2 seconds for JetBrains Mono to load

**Colors look off?**

- Use Chrome/Edge for consistent rendering
- Check color profile settings in OS

---

**Expected Time**: 5-10 minutes total
