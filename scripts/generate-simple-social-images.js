#!/usr/bin/env node
/**
 * Generate simple branded social media images
 * Creates basic OG and Twitter card images with RBP branding
 */

const sharp = require('sharp')
const fs = require('fs')
const path = require('path')

async function generateSimpleSocialImages() {
  console.log('🚀 Generating social media images...\n')

  const publicDir = path.join(__dirname, '../public')

  // Create OG Image (1200x630) - Dark background with green accent
  const ogImageSvg = `
    <svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#0a0a0a;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#1a1a1a;stop-opacity:1" />
        </linearGradient>
        <linearGradient id="text" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" style="stop-color:#00ff00;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#00ffff;stop-opacity:1" />
        </linearGradient>
      </defs>

      <!-- Background -->
      <rect width="1200" height="630" fill="url(#bg)"/>

      <!-- Corner decorations -->
      <rect x="20" y="20" width="60" height="60" fill="none" stroke="#00ff00" stroke-width="2"/>
      <rect x="1120" y="20" width="60" height="60" fill="none" stroke="#00ff00" stroke-width="2"/>
      <rect x="20" y="550" width="60" height="60" fill="none" stroke="#00ff00" stroke-width="2"/>
      <rect x="1120" y="550" width="60" height="60" fill="none" stroke="#00ff00" stroke-width="2"/>

      <!-- Glass container -->
      <rect x="150" y="150" width="900" height="330" rx="16"
            fill="rgba(26, 26, 26, 0.6)"
            stroke="rgba(0, 255, 0, 0.3)"
            stroke-width="2"/>

      <!-- Title -->
      <text x="600" y="280"
            font-family="JetBrains Mono, monospace"
            font-size="72"
            font-weight="bold"
            fill="url(#text)"
            text-anchor="middle">RBP://</text>

      <!-- Subtitle -->
      <text x="600" y="360"
            font-family="JetBrains Mono, monospace"
            font-size="28"
            fill="#c7c7c7"
            text-anchor="middle">AI-Powered Code Review Protocol</text>

      <!-- Features -->
      <text x="300" y="420"
            font-family="JetBrains Mono, monospace"
            font-size="18"
            fill="#00ff00">🔒 Security Scanning</text>
      <text x="580" y="420"
            font-family="JetBrains Mono, monospace"
            font-size="18"
            fill="#00ff00">⚡ Performance</text>
      <text x="850" y="420"
            font-family="JetBrains Mono, monospace"
            font-size="18"
            fill="#00ff00">🤖 AI Reviews</text>

      <!-- Protocol indicator -->
      <text x="600" y="80"
            font-family="JetBrains Mono, monospace"
            font-size="14"
            fill="#00ffff"
            text-anchor="middle"
            opacity="0.8">[ PROTOCOL://ACTIVE ]</text>

      <!-- Footer -->
      <text x="1000" y="590"
            font-family="JetBrains Mono, monospace"
            font-size="14"
            fill="#c7c7c7"
            opacity="0.6">GitHub App Integration</text>
    </svg>
  `

  // Create Twitter Card (1200x675) - Slightly taller
  const twitterCardSvg = ogImageSvg
    .replace('height="630"', 'height="675"')
    .replace('y="550"', 'y="595"')
    .replace('y="590"', 'y="635"')

  try {
    // Generate OG Image
    const ogPath = path.join(publicDir, 'og-image.png')
    await sharp(Buffer.from(ogImageSvg)).png().toFile(ogPath)

    const ogSize = (fs.statSync(ogPath).size / 1024).toFixed(2)
    console.log(`✅ Created og-image.png (1200x630, ${ogSize} KB)`)

    // Generate Twitter Card
    const twitterPath = path.join(publicDir, 'twitter-card.png')
    await sharp(Buffer.from(twitterCardSvg)).png().toFile(twitterPath)

    const twitterSize = (fs.statSync(twitterPath).size / 1024).toFixed(2)
    console.log(`✅ Created twitter-card.png (1200x675, ${twitterSize} KB)`)

    console.log('\n✨ Social media images generated successfully!\n')
    console.log('📊 Summary:')
    console.log(`   - og-image.png: ${ogSize} KB`)
    console.log(`   - twitter-card.png: ${twitterSize} KB`)
    console.log('\n💡 Next steps:')
    console.log('   1. Update app/layout.tsx metadata')
    console.log('   2. Test at https://www.opengraph.xyz/')
    console.log('   3. For better quality, use og-image-template.html\n')
  } catch (error) {
    console.error('❌ Error:', error.message)
    throw error
  }
}

if (require.main === module) {
  generateSimpleSocialImages()
    .then(() => process.exit(0))
    .catch(error => {
      console.error('Failed:', error)
      process.exit(1)
    })
}

module.exports = { generateSimpleSocialImages }
