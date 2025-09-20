#!/usr/bin/env node

/**
 * Environment Validation Script for Git Review Assistant
 * Validates all required environment variables and API connections
 */

const fs = require('fs')
const path = require('path')

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  bold: '\x1b[1m',
}

function log(message, color = 'white') {
  console.log(`${colors[color]}${message}${colors.reset}`)
}

function logHeader(title) {
  log(`\n${colors.bold}${colors.cyan}=== ${title} ===${colors.reset}`)
}

function logSuccess(message) {
  log(`✅ ${message}`, 'green')
}

function logError(message) {
  log(`❌ ${message}`, 'red')
}

function logWarning(message) {
  log(`⚠️  ${message}`, 'yellow')
}

function logInfo(message) {
  log(`ℹ️  ${message}`, 'blue')
}

// Check if file exists
function fileExists(filePath) {
  return fs.existsSync(filePath)
}

// Load environment variables from .env files
function loadEnvFile(filePath) {
  if (!fileExists(filePath)) {
    return null
  }

  const content = fs.readFileSync(filePath, 'utf8')
  const env = {}

  content.split('\n').forEach(line => {
    const trimmed = line.trim()
    if (trimmed && !trimmed.startsWith('#')) {
      const [key, ...valueParts] = trimmed.split('=')
      if (key && valueParts.length > 0) {
        env[key] = valueParts.join('=').replace(/^["']|["']$/g, '')
      }
    }
  })

  return env
}

// Validate individual environment variable
function validateEnvVar(env, key, required = true, description = '') {
  const value = env[key]

  if (!value || value === 'your-' + key.toLowerCase().replace(/_/g, '-')) {
    if (required) {
      logError(`${key} is missing or using placeholder value`)
      if (description) logInfo(`   ${description}`)
      return false
    } else {
      logWarning(`${key} is optional but not set`)
      if (description) logInfo(`   ${description}`)
      return true
    }
  }

  logSuccess(`${key} is set`)
  return true
}

// Test API connection
async function testApiConnection(name, testFn) {
  try {
    logInfo(`Testing ${name} connection...`)
    const result = await testFn()
    if (result) {
      logSuccess(`${name} connection successful`)
      return true
    } else {
      logError(`${name} connection failed`)
      return false
    }
  } catch (error) {
    logError(`${name} connection error: ${error.message}`)
    return false
  }
}

// Test OpenAI API
async function testOpenAI(apiKey) {
  if (!apiKey) return false

  try {
    const response = await fetch('https://api.openai.com/v1/models', {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
    })

    return response.ok
  } catch (error) {
    return false
  }
}

// Main validation function
async function validateEnvironment() {
  logHeader('Git Review Assistant - Environment Validation')

  let allValid = true
  const projectRoot = process.cwd()

  // Check for environment files
  logHeader('Environment Files')

  const frontendEnvPath = path.join(projectRoot, '.env.local')
  const backendEnvPath = path.join(projectRoot, 'backend', '.env')

  if (!fileExists(frontendEnvPath)) {
    logError('.env.local not found in project root')
    logInfo('   Run: cp .env.example .env.local')
    allValid = false
  } else {
    logSuccess('.env.local found')
  }

  if (!fileExists(backendEnvPath)) {
    logError('backend/.env not found')
    logInfo('   Run: cp backend/.env.example backend/.env')
    allValid = false
  } else {
    logSuccess('backend/.env found')
  }

  if (!allValid) {
    logError('Missing environment files. Please create them first.')
    return false
  }

  // Load environment variables
  const frontendEnv = loadEnvFile(frontendEnvPath)
  const backendEnv = loadEnvFile(backendEnvPath)

  // Validate frontend environment
  logHeader('Frontend Environment Variables')

  const frontendValid = [
    validateEnvVar(
      frontendEnv,
      'NEXT_PUBLIC_APP_URL',
      true,
      'Application base URL'
    ),
    validateEnvVar(frontendEnv, 'NEXTAUTH_URL', true, 'NextAuth callback URL'),
    validateEnvVar(
      frontendEnv,
      'NEXTAUTH_SECRET',
      true,
      'NextAuth session encryption key'
    ),
    validateEnvVar(
      frontendEnv,
      'OPENAI_API_KEY',
      true,
      'OpenAI API access key'
    ),
    validateEnvVar(frontendEnv, 'GITHUB_APP_ID', true, 'GitHub App ID number'),
    validateEnvVar(
      frontendEnv,
      'GITHUB_CLIENT_ID',
      true,
      'GitHub OAuth Client ID'
    ),
    validateEnvVar(
      frontendEnv,
      'GITHUB_CLIENT_SECRET',
      true,
      'GitHub OAuth Client Secret'
    ),
    validateEnvVar(
      frontendEnv,
      'GITHUB_PRIVATE_KEY',
      true,
      'GitHub App Private Key (PEM format)'
    ),
    validateEnvVar(
      frontendEnv,
      'GITHUB_WEBHOOK_SECRET',
      true,
      'GitHub Webhook Secret'
    ),
    validateEnvVar(
      frontendEnv,
      'LANGCHAIN_API_KEY',
      false,
      'LangSmith API key for monitoring'
    ),
    validateEnvVar(
      frontendEnv,
      'ANTHROPIC_API_KEY',
      false,
      'Claude API key (optional)'
    ),
  ].every(Boolean)

  // Validate backend environment
  logHeader('Backend Environment Variables')

  const backendValid = [
    validateEnvVar(
      backendEnv,
      'SECRET_KEY',
      true,
      'Backend session encryption key'
    ),
    validateEnvVar(backendEnv, 'OPENAI_API_KEY', true, 'OpenAI API access key'),
    validateEnvVar(backendEnv, 'GITHUB_APP_ID', true, 'GitHub App ID number'),
    validateEnvVar(
      backendEnv,
      'GITHUB_PRIVATE_KEY',
      true,
      'GitHub App Private Key'
    ),
    validateEnvVar(
      backendEnv,
      'GITHUB_WEBHOOK_SECRET',
      true,
      'GitHub Webhook Secret'
    ),
    validateEnvVar(backendEnv, 'ALLOWED_ORIGINS', true, 'CORS allowed origins'),
    validateEnvVar(
      backendEnv,
      'DATABASE_URL',
      true,
      'Database connection string'
    ),
  ].every(Boolean)

  allValid = frontendValid && backendValid && allValid

  // Test API connections
  logHeader('API Connection Tests')

  if (
    frontendEnv.OPENAI_API_KEY &&
    !frontendEnv.OPENAI_API_KEY.startsWith('your-')
  ) {
    const openaiValid = await testApiConnection('OpenAI API', () =>
      testOpenAI(frontendEnv.OPENAI_API_KEY)
    )
    allValid = openaiValid && allValid
  } else {
    logWarning('Skipping OpenAI test - API key not configured')
  }

  // Validate specific formats
  logHeader('Format Validation')

  // Check NextAuth secret length
  if (frontendEnv.NEXTAUTH_SECRET && frontendEnv.NEXTAUTH_SECRET.length < 32) {
    logError('NEXTAUTH_SECRET should be at least 32 characters')
    allValid = false
  } else if (frontendEnv.NEXTAUTH_SECRET) {
    logSuccess('NEXTAUTH_SECRET length is adequate')
  }

  // Check OpenAI API key format
  if (
    frontendEnv.OPENAI_API_KEY &&
    !frontendEnv.OPENAI_API_KEY.startsWith('sk-')
  ) {
    logError('OPENAI_API_KEY should start with "sk-"')
    allValid = false
  } else if (frontendEnv.OPENAI_API_KEY) {
    logSuccess('OPENAI_API_KEY format is correct')
  }

  // Check GitHub Private Key format
  if (
    frontendEnv.GITHUB_PRIVATE_KEY &&
    !frontendEnv.GITHUB_PRIVATE_KEY.includes('BEGIN RSA PRIVATE KEY')
  ) {
    logError('GITHUB_PRIVATE_KEY should be in PEM format')
    allValid = false
  } else if (frontendEnv.GITHUB_PRIVATE_KEY) {
    logSuccess('GITHUB_PRIVATE_KEY format appears correct')
  }

  // Final result
  logHeader('Validation Summary')

  if (allValid) {
    logSuccess('🎉 All environment variables are properly configured!')
    logInfo('You can now run: npm run dev')
    return true
  } else {
    logError('❌ Some environment variables need attention')
    logInfo('Please fix the issues above and run this script again')
    return false
  }
}

// Run validation
if (require.main === module) {
  validateEnvironment().then(success => {
    process.exit(success ? 0 : 1)
  })
}

module.exports = { validateEnvironment }
