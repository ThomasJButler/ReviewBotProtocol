#!/usr/bin/env node
/**
 * Generate favicon PNG files from SVG
 * Uses sharp library for image conversion
 */

const sharp = require('sharp')
const fs = require('fs')
const path = require('path')

async function generateFavicons() {
  console.log('🚀 Generating favicons...\n')

  const svgPath = path.join(__dirname, '../public/favicon.svg')
  const publicDir = path.join(__dirname, '../public')

  if (!fs.existsSync(svgPath)) {
    throw new Error(`SVG file not found: ${svgPath}`)
  }

  const sizes = [16, 32, 64, 128, 256]

  console.log(`📄 Source: ${svgPath}\n`)

  for (const size of sizes) {
    const outputPath = path.join(publicDir, `favicon-${size}x${size}.png`)

    try {
      await sharp(svgPath).resize(size, size).png().toFile(outputPath)

      const fileSize = (fs.statSync(outputPath).size / 1024).toFixed(2)
      console.log(`✅ Created favicon-${size}x${size}.png (${fileSize} KB)`)
    } catch (error) {
      console.error(`❌ Failed to create ${size}x${size}:`, error.message)
    }
  }

  console.log('\n✨ Favicon generation complete!\n')
  console.log('📁 Generated files in public/:')
  sizes.forEach(size => console.log(`   - favicon-${size}x${size}.png`))
  console.log('\n💡 Update app/layout.tsx with new favicon references')
}

if (require.main === module) {
  generateFavicons()
    .then(() => process.exit(0))
    .catch(error => {
      console.error('Error:', error.message)
      process.exit(1)
    })
}

module.exports = { generateFavicons }
