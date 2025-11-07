#!/usr/bin/env node
/**
 * Generate social media images from HTML template
 *
 * This script uses Puppeteer to render the og-image-template.html
 * and create PNG images for social media sharing.
 *
 * Usage: node scripts/generate-social-images.js
 */

const puppeteer = require('puppeteer')
const path = require('path')
const fs = require('fs')

async function generateSocialImages() {
  console.log('🚀 Starting social image generation...\n')

  // Launch browser
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  })

  try {
    const page = await browser.newPage()

    // Path to the HTML template
    const templatePath = path.join(
      __dirname,
      '../public/og-image-template.html'
    )
    const templateUrl = `file://${templatePath}`

    console.log(`📄 Loading template: ${templatePath}`)

    // Navigate to the template
    await page.goto(templateUrl, {
      waitUntil: 'networkidle0',
    })

    // Wait a bit for animations
    await page.waitForTimeout(500)

    // Generate OG Image (1200x630)
    console.log('📸 Generating og-image.png (1200x630)...')
    await page.setViewport({ width: 1200, height: 630 })
    await page.waitForTimeout(200)

    const ogImagePath = path.join(__dirname, '../public/og-image.png')
    await page.screenshot({
      path: ogImagePath,
      type: 'png',
    })
    console.log(`✅ Created: ${ogImagePath}`)

    // Generate Twitter Card (1200x675)
    console.log('📸 Generating twitter-card.png (1200x675)...')
    await page.setViewport({ width: 1200, height: 675 })
    await page.waitForTimeout(200)

    const twitterCardPath = path.join(__dirname, '../public/twitter-card.png')
    await page.screenshot({
      path: twitterCardPath,
      type: 'png',
    })
    console.log(`✅ Created: ${twitterCardPath}`)

    // Get file sizes
    const ogSize = (fs.statSync(ogImagePath).size / 1024).toFixed(2)
    const twitterSize = (fs.statSync(twitterCardPath).size / 1024).toFixed(2)

    console.log('\n✨ Social images generated successfully!\n')
    console.log('📊 File Summary:')
    console.log(`   - og-image.png: ${ogSize} KB`)
    console.log(`   - twitter-card.png: ${twitterSize} KB`)
    console.log('\n💡 Next steps:')
    console.log('   1. Update app/layout.tsx metadata with new images')
    console.log('   2. Test images with https://www.opengraph.xyz/')
    console.log('   3. Commit and push to deploy\n')
  } catch (error) {
    console.error('❌ Error generating images:', error.message)
    throw error
  } finally {
    await browser.close()
  }
}

// Run if called directly
if (require.main === module) {
  generateSocialImages()
    .then(() => {
      console.log('🎉 Done!')
      process.exit(0)
    })
    .catch(error => {
      console.error('Failed to generate images:', error)
      process.exit(1)
    })
}

module.exports = { generateSocialImages }
