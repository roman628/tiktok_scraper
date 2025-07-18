#!/usr/bin/env node

/**
 * TikTok URL Collector
 * Gathers TikTok video URLs from hashtags, users, trending, etc.
 * Does NOT scrape metadata - just collects the URLs for later processing
 */

const { program } = require('commander');
const fs = require('fs-extra');
const path = require('path');
const chalk = require('chalk');
const ora = require('ora');
const csv = require('csv-writer');
const puppeteer = require('puppeteer');

class TikTokURLCollector {
    constructor(options = {}) {
        this.options = {
            outputDir: options.outputDir || 'output',
            headless: options.headless !== false,
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ...options
        };
        
        this.collectedUrls = [];
        this.failedRequests = [];
        this.browser = null;
        this.page = null;
        
        this.setupOutputDirectory();
        this.setupLogger();
    }

    setupOutputDirectory() {
        fs.ensureDirSync(this.options.outputDir);
    }

    setupLogger() {
        this.logFile = path.join(this.options.outputDir, 'url_collection_log.txt');
        this.log(`TikTok URL Collector initialized at ${new Date().toISOString()}`);
    }

    log(message) {
        const timestamp = new Date().toISOString();
        const logEntry = `[${timestamp}] ${message}\n`;
        fs.appendFileSync(this.logFile, logEntry);
        console.log(chalk.gray(`[${timestamp}] ${message}`));
    }

    async initBrowser() {
        this.log('Initializing browser...');
        this.browser = await puppeteer.launch({
            headless: this.options.headless,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        });
        
        this.page = await this.browser.newPage();
        await this.page.setUserAgent(this.options.userAgent);
        await this.page.setViewport({ width: 1920, height: 1080 });
        
        // Block unnecessary resources to speed up
        await this.page.setRequestInterception(true);
        this.page.on('request', (req) => {
            const resourceType = req.resourceType();
            if (['image', 'stylesheet', 'font'].includes(resourceType)) {
                req.abort();
            } else {
                req.continue();
            }
        });
    }

    async closeBrowser() {
        if (this.browser) {
            await this.browser.close();
            this.browser = null;
            this.page = null;
        }
    }

    async collectFromHashtag(hashtag, count = 50) {
        const spinner = ora(`Collecting URLs from hashtag: #${hashtag}`).start();
        
        try {
            this.log(`Starting URL collection for hashtag #${hashtag} (target: ${count} URLs)`);
            
            if (!this.browser) {
                await this.initBrowser();
            }

            const hashtagUrl = `https://www.tiktok.com/tag/${hashtag}`;
            this.log(`Navigating to: ${hashtagUrl}`);
            
            await this.page.goto(hashtagUrl, { waitUntil: 'networkidle2', timeout: 30000 });
            
            // Wait for videos to load - try multiple selectors
            try {
                await this.page.waitForSelector('[data-e2e="challenge-item"]', { timeout: 10000 });
            } catch (e) {
                // Try alternative selector
                await this.page.waitForSelector('a[href*="/video/"]', { timeout: 10000 });
            }
            
            const urls = await this.extractVideoUrls(count);
            
            this.collectedUrls.push(...urls.map(url => ({
                url,
                source: 'hashtag',
                query: hashtag,
                collectedAt: new Date().toISOString()
            })));
            
            spinner.succeed(chalk.green(`✅ Collected ${urls.length} URLs from #${hashtag}`));
            this.log(`Successfully collected ${urls.length} URLs from hashtag #${hashtag}`);
            
            return urls;
            
        } catch (error) {
            spinner.fail(chalk.red(`❌ Failed to collect from hashtag #${hashtag}: ${error.message}`));
            this.log(`Failed to collect from hashtag #${hashtag}: ${error.message}`);
            
            this.failedRequests.push({
                type: 'hashtag',
                query: hashtag,
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            throw error;
        }
    }

    async collectFromUser(username, count = 50) {
        const spinner = ora(`Collecting URLs from user: @${username}`).start();
        
        try {
            this.log(`Starting URL collection for user @${username} (target: ${count} URLs)`);
            
            if (!this.browser) {
                await this.initBrowser();
            }

            const userUrl = `https://www.tiktok.com/@${username}`;
            this.log(`Navigating to: ${userUrl}`);
            
            await this.page.goto(userUrl, { waitUntil: 'networkidle2', timeout: 30000 });
            
            // Wait for videos to load - try multiple selectors
            try {
                await this.page.waitForSelector('[data-e2e="user-post-item"]', { timeout: 10000 });
            } catch (e) {
                // Try alternative selector
                await this.page.waitForSelector('a[href*="/video/"]', { timeout: 10000 });
            }
            
            const urls = await this.extractVideoUrls(count);
            
            this.collectedUrls.push(...urls.map(url => ({
                url,
                source: 'user',
                query: username,
                collectedAt: new Date().toISOString()
            })));
            
            spinner.succeed(chalk.green(`✅ Collected ${urls.length} URLs from @${username}`));
            this.log(`Successfully collected ${urls.length} URLs from user @${username}`);
            
            return urls;
            
        } catch (error) {
            spinner.fail(chalk.red(`❌ Failed to collect from user @${username}: ${error.message}`));
            this.log(`Failed to collect from user @${username}: ${error.message}`);
            
            this.failedRequests.push({
                type: 'user',
                query: username,
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            throw error;
        }
    }

    async collectTrending(count = 50) {
        const spinner = ora(`Collecting URLs from trending/discover`).start();
        
        try {
            this.log(`Starting URL collection from trending (target: ${count} URLs)`);
            
            if (!this.browser) {
                await this.initBrowser();
            }

            const trendingUrl = 'https://www.tiktok.com/foryou';
            this.log(`Navigating to: ${trendingUrl}`);
            
            await this.page.goto(trendingUrl, { waitUntil: 'networkidle2', timeout: 30000 });
            
            // Wait for videos to load - try multiple selectors
            try {
                await this.page.waitForSelector('[data-e2e="recommend-list-item-container"]', { timeout: 10000 });
            } catch (e) {
                // Try alternative selector
                await this.page.waitForSelector('a[href*="/video/"]', { timeout: 10000 });
            }
            
            const urls = await this.extractVideoUrls(count);
            
            this.collectedUrls.push(...urls.map(url => ({
                url,
                source: 'trending',
                query: 'foryou',
                collectedAt: new Date().toISOString()
            })));
            
            spinner.succeed(chalk.green(`✅ Collected ${urls.length} URLs from trending`));
            this.log(`Successfully collected ${urls.length} URLs from trending`);
            
            return urls;
            
        } catch (error) {
            spinner.fail(chalk.red(`❌ Failed to collect from trending: ${error.message}`));
            this.log(`Failed to collect from trending: ${error.message}`);
            
            this.failedRequests.push({
                type: 'trending',
                query: 'foryou',
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            throw error;
        }
    }

    async extractVideoUrls(targetCount) {
        const urls = new Set();
        let scrollAttempts = 0;
        const maxScrollAttempts = 10;
        
        while (urls.size < targetCount && scrollAttempts < maxScrollAttempts) {
            // Extract video URLs from current page
            const pageUrls = await this.page.evaluate(() => {
                const links = Array.from(document.querySelectorAll('a[href*="/video/"]'));
                return links
                    .map(link => link.href)
                    .filter(href => href.includes('/video/'))
                    .filter(href => href.match(/\/video\/\d+/));
            });
            
            pageUrls.forEach(url => urls.add(url));
            
            this.log(`Extracted ${pageUrls.length} URLs, total unique: ${urls.size}/${targetCount}`);
            
            if (urls.size >= targetCount) {
                break;
            }
            
            // Scroll to load more content
            await this.page.evaluate(() => {
                window.scrollTo(0, document.body.scrollHeight);
            });
            
            // Wait for new content to load
            await this.delay(2000);
            scrollAttempts++;
        }
        
        return Array.from(urls).slice(0, targetCount);
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async saveResults(format = 'json') {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        
        switch (format.toLowerCase()) {
            case 'json':
                await this.saveAsJSON(timestamp);
                break;
            case 'csv':
                await this.saveAsCSV(timestamp);
                break;
            case 'txt':
                await this.saveAsTXT(timestamp);
                break;
            case 'all':
                await this.saveAsJSON(timestamp);
                await this.saveAsCSV(timestamp);
                await this.saveAsTXT(timestamp);
                break;
            default:
                throw new Error(`Unsupported format: ${format}`);
        }
        
        if (this.failedRequests.length > 0) {
            await this.saveFailedRequests(timestamp);
        }
    }

    async saveAsJSON(timestamp) {
        const filename = `tiktok_urls_${timestamp}.json`;
        const filepath = path.join(this.options.outputDir, filename);
        
        await fs.writeJSON(filepath, this.collectedUrls, { spaces: 2 });
        this.log(`Saved ${this.collectedUrls.length} URLs to ${filename}`);
        console.log(chalk.green(`✅ JSON saved: ${filename}`));
    }

    async saveAsCSV(timestamp) {
        const filename = `tiktok_urls_${timestamp}.csv`;
        const filepath = path.join(this.options.outputDir, filename);
        
        const csvWriter = csv.createObjectCsvWriter({
            path: filepath,
            header: [
                { id: 'url', title: 'TikTok URL' },
                { id: 'source', title: 'Source Type' },
                { id: 'query', title: 'Query/Source' },
                { id: 'collectedAt', title: 'Collected At' }
            ]
        });
        
        await csvWriter.writeRecords(this.collectedUrls);
        this.log(`Saved ${this.collectedUrls.length} URLs to ${filename}`);
        console.log(chalk.green(`✅ CSV saved: ${filename}`));
    }

    async saveAsTXT(timestamp) {
        const filename = `tiktok_urls_${timestamp}.txt`;
        const filepath = path.join(this.options.outputDir, filename);
        
        const urls = this.collectedUrls.map(item => item.url);
        
        await fs.writeFile(filepath, urls.join('\n'));
        this.log(`Saved ${urls.length} URLs to ${filename}`);
        console.log(chalk.green(`✅ TXT saved: ${filename}`));
    }

    async saveFailedRequests(timestamp) {
        const filename = `failed_collections_${timestamp}.json`;
        const filepath = path.join(this.options.outputDir, filename);
        
        await fs.writeJSON(filepath, this.failedRequests, { spaces: 2 });
        this.log(`Saved ${this.failedRequests.length} failed requests to ${filename}`);
        console.log(chalk.yellow(`⚠️ Failed requests saved: ${filename}`));
    }

    generateReport() {
        const totalUrls = this.collectedUrls.length;
        const failedCount = this.failedRequests.length;
        const sourceBreakdown = {};
        
        this.collectedUrls.forEach(item => {
            sourceBreakdown[item.source] = (sourceBreakdown[item.source] || 0) + 1;
        });
        
        console.log('\n' + chalk.bold('📊 URL COLLECTION REPORT'));
        console.log('═'.repeat(50));
        console.log(chalk.green(`✅ Total URLs Collected: ${totalUrls}`));
        console.log(chalk.red(`❌ Failed Requests: ${failedCount}`));
        
        console.log('\n' + chalk.bold('📋 Source Breakdown:'));
        Object.entries(sourceBreakdown).forEach(([source, count]) => {
            console.log(`  ${source}: ${count} URLs`);
        });
        
        if (totalUrls > 0) {
            console.log('\n' + chalk.bold('🔗 Sample URLs:'));
            this.collectedUrls.slice(0, 5).forEach((item, index) => {
                console.log(`${index + 1}. ${item.url} (from ${item.source}: ${item.query})`);
            });
        }
        
        return {
            totalUrls,
            failedCount,
            sourceBreakdown
        };
    }
}

// CLI Interface
const VERSION = '1.0.0';

const banner = `
██╗   ██╗██████╗ ██╗          ██████╗ ██████╗ ██╗     ██╗     ███████╗ ██████╗████████╗ ██████╗ ██████╗ 
██║   ██║██╔══██╗██║         ██╔════╝██╔═══██╗██║     ██║     ██╔════╝██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██║   ██║██████╔╝██║         ██║     ██║   ██║██║     ██║     █████╗  ██║        ██║   ██║   ██║██████╔╝
██║   ██║██╔══██╗██║         ██║     ██║   ██║██║     ██║     ██╔══╝  ██║        ██║   ██║   ██║██╔══██╗
╚██████╔╝██║  ██║███████╗    ╚██████╗╚██████╔╝███████╗███████╗███████╗╚██████╗   ██║   ╚██████╔╝██║  ██║
 ╚═════╝ ╚═╝  ╚═╝╚══════╝     ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
`;

function showBanner() {
    console.log(chalk.cyan(banner));
    console.log(chalk.yellow(`                              Version ${VERSION} - TikTok URL Collector`));
    console.log(chalk.gray('                              Gathers TikTok video URLs for batch processing'));
    console.log();
}

async function main() {
    program
        .name('tiktok-url-collector')
        .description('Collect TikTok video URLs from hashtags, users, and trending')
        .version(VERSION);

    program
        .command('hashtag')
        .description('Collect URLs from a hashtag page')
        .argument('<hashtag>', 'Hashtag to collect from (without #)')
        .option('-c, --count <number>', 'Number of URLs to collect', '50')
        .option('-o, --output <directory>', 'Output directory', 'output')
        .option('-f, --format <format>', 'Output format (json, csv, txt, all)', 'json')
        .option('--headless', 'Run browser in headless mode', true)
        .action(async (hashtag, options) => {
            showBanner();
            console.log(chalk.green(`🏷️  Collecting URLs from hashtag: #${hashtag}`));
            console.log(chalk.gray(`Target: ${options.count} URLs`));
            console.log();

            const collector = new TikTokURLCollector({
                outputDir: options.output,
                headless: options.headless
            });

            try {
                await collector.collectFromHashtag(hashtag, parseInt(options.count));
                await collector.saveResults(options.format);
                collector.generateReport();
                console.log(chalk.green('\n✅ URL collection completed successfully!'));
            } catch (error) {
                console.error(chalk.red(`❌ Error: ${error.message}`));
                process.exit(1);
            } finally {
                await collector.closeBrowser();
            }
        });

    program
        .command('user')
        .description('Collect URLs from a user profile')
        .argument('<username>', 'Username to collect from (without @)')
        .option('-c, --count <number>', 'Number of URLs to collect', '50')
        .option('-o, --output <directory>', 'Output directory', 'output')
        .option('-f, --format <format>', 'Output format (json, csv, txt, all)', 'json')
        .option('--headless', 'Run browser in headless mode', true)
        .action(async (username, options) => {
            showBanner();
            console.log(chalk.green(`👤 Collecting URLs from user: @${username}`));
            console.log(chalk.gray(`Target: ${options.count} URLs`));
            console.log();

            const collector = new TikTokURLCollector({
                outputDir: options.output,
                headless: options.headless
            });

            try {
                await collector.collectFromUser(username, parseInt(options.count));
                await collector.saveResults(options.format);
                collector.generateReport();
                console.log(chalk.green('\n✅ URL collection completed successfully!'));
            } catch (error) {
                console.error(chalk.red(`❌ Error: ${error.message}`));
                process.exit(1);
            } finally {
                await collector.closeBrowser();
            }
        });

    program
        .command('trending')
        .description('Collect URLs from trending/for you page')
        .option('-c, --count <number>', 'Number of URLs to collect', '50')
        .option('-o, --output <directory>', 'Output directory', 'output')
        .option('-f, --format <format>', 'Output format (json, csv, txt, all)', 'json')
        .option('--headless', 'Run browser in headless mode', true)
        .action(async (options) => {
            showBanner();
            console.log(chalk.green(`🔥 Collecting URLs from trending/for you`));
            console.log(chalk.gray(`Target: ${options.count} URLs`));
            console.log();

            const collector = new TikTokURLCollector({
                outputDir: options.output,
                headless: options.headless
            });

            try {
                await collector.collectTrending(parseInt(options.count));
                await collector.saveResults(options.format);
                collector.generateReport();
                console.log(chalk.green('\n✅ URL collection completed successfully!'));
            } catch (error) {
                console.error(chalk.red(`❌ Error: ${error.message}`));
                process.exit(1);
            } finally {
                await collector.closeBrowser();
            }
        });

    program.parse();

    if (!process.argv.slice(2).length) {
        showBanner();
        console.log(chalk.yellow('🚀 Welcome to the TikTok URL Collector!'));
        console.log(chalk.gray('Gather TikTok video URLs for batch processing.'));
        console.log();
        console.log(chalk.cyan('Examples:'));
        console.log(chalk.white('  node url_collector.js hashtag funny -c 100 -f all'));
        console.log(chalk.white('  node url_collector.js user zachking -c 50 -f txt'));
        console.log(chalk.white('  node url_collector.js trending -c 200'));
        console.log();
        program.help();
    }
}

if (require.main === module) {
    main();
}

module.exports = TikTokURLCollector;