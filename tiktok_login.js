#!/usr/bin/env node

/**
 * TikTok Login Script
 * Opens Firefox visibly so you can manually log in to TikTok
 * Saves the session/cookies for future automated use
 */

const { firefox } = require('playwright');
const fs = require('fs-extra');
const path = require('path');
const chalk = require('chalk');

class TikTokLogin {
    constructor() {
        this.browser = null;
        this.context = null;
        this.page = null;
        this.cookieFile = path.join(__dirname, 'tiktok_session.json');
    }

    async init() {
        console.log(chalk.cyan('🦊 TikTok Login Helper'));
        console.log(chalk.gray('This will open Firefox so you can manually log in to TikTok'));
        console.log(chalk.yellow('Note: This will use your system Firefox installation'));
        console.log();

        // Launch Playwright Firefox in visible mode with stealth settings
        this.browser = await firefox.launch({
            headless: false,
            firefoxUserPrefs: {
                'dom.webdriver.enabled': false,
                'useAutomationExtension': false,
                'general.platform.override': 'Win32',
                'general.useragent.override': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
            }
        });

        // Create a persistent context to save session data
        this.context = await this.browser.newContext({
            viewport: { width: 1920, height: 1080 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            extraHTTPHeaders: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        });

        // Load existing cookies if they exist
        if (await fs.pathExists(this.cookieFile)) {
            console.log(chalk.yellow('📦 Loading existing session...'));
            try {
                const sessionData = await fs.readJson(this.cookieFile);
                if (sessionData.cookies) {
                    await this.context.addCookies(sessionData.cookies);
                    console.log(chalk.green('✅ Existing session loaded'));
                }
            } catch (error) {
                console.log(chalk.red('❌ Failed to load existing session:', error.message));
            }
        }

        this.page = await this.context.newPage();

        // Add stealth scripts
        await this.page.addInitScript(() => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(window, 'chrome', {
                get: () => ({
                    runtime: {},
                }),
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        });

        console.log(chalk.green('🚀 Firefox launched successfully'));
    }

    async login() {
        console.log(chalk.blue('🌐 Navigating to TikTok...'));
        await this.page.goto('https://www.tiktok.com', { waitUntil: 'domcontentloaded' });
        
        console.log();
        console.log(chalk.yellow('👤 Please log in to TikTok manually in the Firefox window'));
        console.log(chalk.gray('   - Click the "Log in" button'));
        console.log(chalk.gray('   - Use your preferred login method (phone, email, etc.)'));
        console.log(chalk.gray('   - Complete any verification steps'));
        console.log(chalk.gray('   - Navigate to a user profile to verify videos are visible'));
        console.log();
        console.log(chalk.cyan('⏳ Press ENTER in this terminal when you\'re logged in and can see videos...'));

        // Wait for user input
        await this.waitForUserInput();

        // Check if login was successful
        const isLoggedIn = await this.checkLoginStatus();
        
        if (isLoggedIn) {
            console.log(chalk.green('✅ Login successful!'));
            await this.saveSession();
            console.log(chalk.green('💾 Session saved successfully'));
            return true;
        } else {
            console.log(chalk.red('❌ Login verification failed'));
            return false;
        }
    }

    async checkLoginStatus() {
        try {
            // Check for login indicators
            const isLoggedIn = await this.page.evaluate(() => {
                // Look for profile menu or logged-in indicators
                const profileMenu = document.querySelector('[data-e2e="profile-icon"]');
                const uploadButton = document.querySelector('[data-e2e="upload-icon"]');
                const loginButton = document.querySelector('[data-e2e="login-button"]');
                
                // If we find profile/upload icons and no login button, we're likely logged in
                return (profileMenu || uploadButton) && !loginButton;
            });

            // Also check if we can see the current URL
            const currentUrl = this.page.url();
            console.log(chalk.gray(`Current URL: ${currentUrl}`));

            return isLoggedIn;
        } catch (error) {
            console.log(chalk.red('Error checking login status:', error.message));
            return false;
        }
    }

    async saveSession() {
        try {
            // Get all cookies from the context
            const cookies = await this.context.cookies();
            
            // Get local storage and session storage
            const storageState = await this.context.storageState();
            
            const sessionData = {
                cookies,
                storageState,
                timestamp: new Date().toISOString(),
                userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
            };

            await fs.writeJson(this.cookieFile, sessionData, { spaces: 2 });
            console.log(chalk.green(`📁 Session saved to: ${this.cookieFile}`));
            
        } catch (error) {
            console.log(chalk.red('❌ Failed to save session:', error.message));
            throw error;
        }
    }

    async waitForUserInput() {
        return new Promise((resolve) => {
            process.stdin.once('data', () => {
                resolve();
            });
        });
    }

    async testSession() {
        console.log(chalk.blue('🧪 Testing saved session...'));
        
        // Navigate to a test user profile
        await this.page.goto('https://www.tiktok.com/@fluxconvos', { waitUntil: 'domcontentloaded' });
        await this.page.waitForTimeout(5000);

        // Check if videos are visible
        const videoCount = await this.page.locator('a[href*="/video/"]').count();
        
        if (videoCount > 0) {
            console.log(chalk.green(`✅ Session test successful! Found ${videoCount} video links`));
            return true;
        } else {
            console.log(chalk.yellow('⚠️  No videos found - session may need refresh'));
            return false;
        }
    }

    async close() {
        if (this.browser) {
            await this.browser.close();
        }
    }
}

async function main() {
    const loginHelper = new TikTokLogin();
    
    try {
        await loginHelper.init();
        
        const success = await loginHelper.login();
        
        if (success) {
            console.log();
            console.log(chalk.cyan('🧪 Testing the saved session...'));
            const testResult = await loginHelper.testSession();
            
            if (testResult) {
                console.log();
                console.log(chalk.green('🎉 All done! Your TikTok session has been saved.'));
                console.log(chalk.gray('You can now use the URL collector with your authenticated session.'));
            }
        }
        
        console.log();
        console.log(chalk.blue('🔥 Keep the browser open to continue testing, or close it to exit.'));
        console.log(chalk.gray('Press ENTER to close the browser and exit...'));
        await loginHelper.waitForUserInput();
        
    } catch (error) {
        console.error(chalk.red('❌ Error:', error.message));
    } finally {
        await loginHelper.close();
    }
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = TikTokLogin;