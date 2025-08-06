// Live HTML fetcher for Stake.com provider collection page
const Scrappey = require('scrappey-wrapper');
const fs = require('fs');

// Initialize Scrappey with your API key
const scrappey = new Scrappey('CPLgrNtC9kgMlgvBpMLydXJU3wIYVhD9bvxKn0ZO8SRWPNJvpgu4Ezhwki1U');

async function fetchStakeProviderGames(providerSlug = 'pragmatic-play') {
    const maxRetries = 3;
    const retryDelay = 3000; // 3 seconds
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`🚀 Starting live fetch of Stake.com games for provider: ${providerSlug} (attempt ${attempt}/${maxRetries})...`);
            
            // Create session with residential proxy (US)
            const session = await scrappey.createSession({
                proxy: {
                    country: 'US'
                }
            });
            
            console.log('✅ Session created successfully:', session.session);
            
            // Make request to specific provider games page
            const url = `https://stake.com/casino/group/${providerSlug}`;
            console.log(`📡 Fetching: ${url}`);
            
            const response = await scrappey.get({
                url: url,
                session: session.session
            });
            
            console.log('✅ Successfully fetched live HTML content');
            console.log('📊 Response status:', response.status);
            console.log('📋 Response structure:', Object.keys(response));
            
            // Check the actual response structure
            let htmlContent;
            if (response.solution && response.solution.response) {
                htmlContent = response.solution.response;
            } else if (response.response) {
                htmlContent = response.response;
            } else if (response.html) {
                htmlContent = response.html;
            } else if (response.content) {
                htmlContent = response.content;
            } else if (response.solution && response.solution.innerText) {
                htmlContent = response.solution.innerText;
            } else if (response.data) {
                htmlContent = response.data;
            } else {
                console.log(`❌ Could not find HTML content in response (attempt ${attempt})`);
                console.log('📋 Available keys:', Object.keys(response));
                console.log('📄 Response preview:', JSON.stringify(response).substring(0, 500));
                
                if (attempt < maxRetries) {
                    console.log(`⏳ Retrying in ${retryDelay / 1000} seconds...`);
                    // Clean up session before retry
                    try {
                        await scrappey.destroySession(session.session);
                    } catch (e) {
                        console.log('Warning: Could not destroy session:', e.message);
                    }
                    await new Promise(resolve => setTimeout(resolve, retryDelay * attempt));
                    continue;
                } else {
                    throw new Error('Could not find HTML content in response after all retries');
                }
            }
            
            console.log('📏 Content length:', htmlContent.length, 'characters');
            
            // Generate timestamp for filename
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const filename = `stake_games_${providerSlug}_${timestamp}.html`;
            
            // Save the fresh HTML content
            fs.writeFileSync(filename, htmlContent);
            console.log(`💾 Games HTML saved to: ${filename}`);
            
            // Analyze the content
            analyzeGamesContent(htmlContent, filename, providerSlug);
            
            // Also save as latest.html for easy access
            fs.writeFileSync(`stake_games_${providerSlug}_latest.html`, htmlContent);
            console.log(`💾 Also saved as: stake_games_${providerSlug}_latest.html`);
            
            // Destroy session to clean up
            await scrappey.destroySession(session.session);
            console.log('🧹 Session cleaned up');
            
            console.log(`🎉 Successfully fetched ${providerSlug} games page!`);
            return htmlContent;
            
        } catch (error) {
            console.error(`❌ Error on attempt ${attempt} for ${providerSlug}:`, error.message);
            
            if (attempt < maxRetries) {
                const waitTime = retryDelay * attempt;
                console.log(`⏳ Retrying in ${waitTime / 1000} seconds...`);
                await new Promise(resolve => setTimeout(resolve, waitTime));
            } else {
                console.error(`💥 All ${maxRetries} attempts failed for ${providerSlug}`);
                throw error;
            }
        }
    }
}

function analyzeGamesContent(htmlContent, filename, providerSlug) {
    try {
        // Look for game-related content
        const gameMatches = htmlContent.match(/game|slot|casino|play/gi);
        if (gameMatches) {
            console.log(`🎰 Found ${gameMatches.length} game-related mentions`);
        }
        
        // Extract title
        const titleMatch = htmlContent.match(/<title>(.*?)<\/title>/);
        if (titleMatch) {
            console.log(`� Page title: ${titleMatch[1]}`);
        }
        
        // Look for total games count
        const totalGamePatterns = [
            /Displaying\s+\d+\s+of\s+(\d+)\s+games/i,
            /(\d+)\s+games/i,
            /total["\']:\s*(\d+)/i,
            /gameCount["\']:\s*(\d+)/i
        ];
        
        let totalGames = 0;
        for (const pattern of totalGamePatterns) {
            const match = htmlContent.match(pattern);
            if (match) {
                totalGames = parseInt(match[1]);
                console.log(`� Total games found: ${totalGames}`);
                break;
            }
        }
        
        // Look for initial games displayed
        const gameDataMatches = htmlContent.match(/thumbnailUrl|"name":/g);
        if (gameDataMatches) {
            console.log(`🎮 Found approximately ${gameDataMatches.length / 2} games in initial load`);
        }
        
        // Look for JSON data in script tags
        const scriptMatches = htmlContent.match(/<script[^>]*>[\s\S]*?<\/script>/g);
        let jsonGameCount = 0;
        if (scriptMatches) {
            for (const script of scriptMatches) {
                const gameObjects = script.match(/\{[^{}]*"thumbnailUrl"[^{}]*\}/g);
                if (gameObjects) {
                    jsonGameCount += gameObjects.length;
                }
            }
        }
        
        if (jsonGameCount > 0) {
            console.log(`📊 Found ${jsonGameCount} games in JSON data`);
        }
        
        console.log(`🎉 Successfully fetched and analyzed games for ${providerSlug}!`);
        
    } catch (error) {
        console.log('⚠️ Error analyzing content:', error.message);
    }
}

// Function for continuous monitoring
async function continuousMonitoring(providerSlug, intervalMinutes = 30) {
    console.log(`🔄 Starting continuous monitoring for ${providerSlug} every ${intervalMinutes} minutes...`);
    
    // Fetch immediately on start
    await fetchStakeProviderGames(providerSlug);
    
    // Set up interval for continuous fetching
    setInterval(async () => {
        console.log(`\n⏰ Scheduled fetch for ${providerSlug} starting...`);
        try {
            await fetchStakeProviderGames(providerSlug);
        } catch (error) {
            console.error('❌ Scheduled fetch failed:', error.message);
        }
    }, intervalMinutes * 60 * 1000);
}

// Main execution
async function main() {
    const args = process.argv.slice(2);
    
    // Parse command line arguments
    const providerArg = args.find(arg => arg.startsWith('--provider='));
    const provider = providerArg ? providerArg.split('=')[1] : 'pragmatic-play';
    
    if (args.includes('--continuous') || args.includes('-c')) {
        const intervalArg = args.find(arg => arg.startsWith('--interval='));
        const interval = intervalArg ? parseInt(intervalArg.split('=')[1]) : 30;
        await continuousMonitoring(provider, interval);
    } else {
        // Single fetch
        await fetchStakeProviderGames(provider);
    }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Gracefully shutting down...');
    process.exit(0);
});

// Run the script
if (require.main === module) {
    main().catch(error => {
        console.error('💥 Fatal error:', error);
        process.exit(1);
    });
}

module.exports = { fetchStakeProviderGames, continuousMonitoring };
