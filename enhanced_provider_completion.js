// Enhanced Provider Completion System
// Properly manages offsets, checkpoints, and directory structure

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { parseStakeResponse } = require('./data_parser.js');

// Configuration
const CONFIG = {
    GAMES_PER_REQUEST: 39,
    MIN_OFFSET: 39, // Start from 39 as specified
    MAX_RETRIES: 6, // Increased retries for robustness
    DELAY_BETWEEN_REQUESTS: 5000, // 5 seconds between requests
    DELAY_BETWEEN_RETRIES: 8000, // 8 seconds between retries
    WORKING_FETCHER: './simple_fetcher.js', // The working fetcher
    CHECKPOINTS_DIR: './checkpoints/',
    STAKE_THUMBNAILS_DIR: './stake_thumbnails/',
    REQUEST_TIMEOUT: 180000 // 3 minutes timeout
};

/**
 * Scan checkpoints directory to find all providers
 * @returns {Array} List of all providers with their status
 */
function scanAllProviders() {
    const providers = [];
    
    try {
        if (!fs.existsSync(CONFIG.CHECKPOINTS_DIR)) {
            console.log('⚠️ Checkpoints directory not found');
            return providers;
        }
        
        const files = fs.readdirSync(CONFIG.CHECKPOINTS_DIR)
            .filter(f => f.startsWith('provider_') && f.endsWith('.json'));
        
        console.log(`📁 Found ${files.length} provider checkpoint files`);
        
        files.forEach(file => {
            try {
                const filePath = path.join(CONFIG.CHECKPOINTS_DIR, file);
                const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
                
                const remaining = data.total_games - data.games_fetched;
                const needsCompletion = !data.is_complete && data.needs_pagination && remaining > 0;
                
                providers.push({
                    slug: data.provider_slug,
                    name: data.provider_name,
                    totalGames: data.total_games,
                    fetchedGames: data.games_fetched,
                    remainingGames: remaining,
                    isComplete: data.is_complete,
                    needsPagination: data.needs_pagination,
                    needsCompletion: needsCompletion,
                    outputDir: data.output_dir,
                    gamesDataFile: data.games_data_file,
                    checkpointFile: filePath,
                    status: data.status
                });
                
                if (needsCompletion) {
                    console.log(`📦 ${data.provider_name}: ${remaining} games remaining (${data.games_fetched}/${data.total_games})`);
                }
                
            } catch (error) {
                console.log(`⚠️ Skipping invalid checkpoint file: ${file} - ${error.message}`);
            }
        });
        
    } catch (error) {
        console.error(`❌ Error scanning checkpoints: ${error.message}`);
    }
    
    return providers;
}

/**
 * Execute a single GraphQL request with proper offset management
 * @param {string} providerSlug - Provider slug
 * @param {number} offset - Exact offset for the request
 * @param {number} limit - Number of games to fetch
 * @returns {Promise<Object>} Parsed response data
 */
async function executeSingleRequest(providerSlug, offset, limit) {
    return new Promise((resolve, reject) => {
        console.log(`🚀 Executing: node ${CONFIG.WORKING_FETCHER} ${providerSlug} ${offset} ${limit}`);
        
        const process = spawn('node', [CONFIG.WORKING_FETCHER, providerSlug, offset.toString(), limit.toString()], {
            stdio: 'pipe',
            cwd: __dirname
        });
        
        let output = '';
        let errorOutput = '';
        
        process.stdout.on('data', (data) => {
            output += data.toString();
        });
        
        process.stderr.on('data', (data) => {
            errorOutput += data.toString();
        });
        
        process.on('close', (code) => {
            if (code === 0) {
                // Find the most recent response file
                const files = fs.readdirSync('./')
                    .filter(f => f.includes(providerSlug) && f.includes('stake_raw_response') && f.includes('2025'))
                    .sort()
                    .reverse();
                
                if (files.length > 0) {
                    const responseFile = files[0];
                    console.log(`📁 Found response file: ${responseFile}`);
                    
                    try {
                        const responseData = fs.readFileSync(responseFile, 'utf8');
                        const parsed = parseStakeResponse(responseData);
                        
                        if (parsed.success && parsed.games && parsed.games.length > 0) {
                            resolve(parsed);
                        } else {
                            reject(new Error(`No games found in response: ${parsed.error || 'Unknown error'}`));
                        }
                    } catch (error) {
                        reject(new Error(`Failed to parse response: ${error.message}`));
                    }
                } else {
                    reject(new Error('No response file found'));
                }
            } else {
                reject(new Error(`GraphQL fetcher failed with code ${code}: ${errorOutput}`));
            }
        });
        
        // Set timeout
        setTimeout(() => {
            process.kill('SIGTERM');
            reject(new Error('Request timeout'));
        }, CONFIG.REQUEST_TIMEOUT);
    });
}

/**
 * Ensure directory structure exists
 * @param {string} dirPath - Directory path to create
 */
function ensureDirectoryExists(dirPath) {
    if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
        console.log(`📁 Created directory: ${dirPath}`);
    }
}

/**
 * Load existing games data for a provider
 * @param {Object} provider - Provider info
 * @returns {Array} Existing games array
 */
function loadExistingGames(provider) {
    try {
        if (fs.existsSync(provider.gamesDataFile)) {
            const data = JSON.parse(fs.readFileSync(provider.gamesDataFile, 'utf8'));
            return data.games || [];
        }
    } catch (error) {
        console.log(`⚠️ Could not load existing games: ${error.message}`);
    }
    return [];
}

/**
 * Save games data to provider directory
 * @param {Object} provider - Provider info
 * @param {Array} allGames - All games for this provider
 * @param {number} currentOffset - Current fetch offset
 */
function saveProviderData(provider, allGames, currentOffset) {
    try {
        // Ensure output directory exists
        ensureDirectoryExists(provider.outputDir);
        
        // Prepare data structure
        const gameData = {
            timestamp: new Date().toISOString(),
            provider: {
                id: provider.slug,
                name: provider.name,
                slug: provider.slug
            },
            summary: {
                totalGames: provider.totalGames,
                fetchedGames: allGames.length,
                remainingGames: Math.max(0, provider.totalGames - allGames.length),
                isComplete: allGames.length >= provider.totalGames,
                currentOffset: currentOffset
            },
            games: allGames
        };
        
        // Save to provider directory
        fs.writeFileSync(provider.gamesDataFile, JSON.stringify(gameData, null, 2));
        console.log(`💾 Saved ${allGames.length} games to: ${provider.gamesDataFile}`);
        
        // Update checkpoint
        const checkpointData = JSON.parse(fs.readFileSync(provider.checkpointFile, 'utf8'));
        checkpointData.games_fetched = allGames.length;
        checkpointData.is_complete = allGames.length >= provider.totalGames;
        checkpointData.timestamp = new Date().toISOString();
        checkpointData.status = allGames.length >= provider.totalGames ? 'completed' : 'in_progress';
        
        fs.writeFileSync(provider.checkpointFile, JSON.stringify(checkpointData, null, 2));
        console.log(`💾 Updated checkpoint: ${provider.checkpointFile}`);
        
        return true;
    } catch (error) {
        console.error(`❌ Failed to save data: ${error.message}`);
        return false;
    }
}

/**
 * Complete a single provider by fetching all remaining games
 * @param {Object} provider - Provider info
 * @returns {Promise<Object>} Completion result
 */
async function completeProvider(provider) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`🎯 Starting completion for: ${provider.name}`);
    console.log(`📊 Total: ${provider.totalGames}, Fetched: ${provider.fetchedGames}, Remaining: ${provider.remainingGames}`);
    console.log(`📁 Output directory: ${provider.outputDir}`);
    console.log(`${'='.repeat(80)}`);
    
    // Load existing games
    const existingGames = loadExistingGames(provider);
    console.log(`📚 Loaded ${existingGames.length} existing games`);
    
    let allGames = [...existingGames];
    
    // Calculate correct next offset
    // If we have 39 games (from offset 0), next offset should be 39 (to get games 40+)
    let currentOffset = existingGames.length; // Start from where we left off
    let requestCount = 0;
    const maxRequests = Math.ceil(provider.remainingGames / CONFIG.GAMES_PER_REQUEST);
    
    console.log(`📋 Starting from offset: ${currentOffset} (already have games 0-${existingGames.length - 1})`);
    console.log(`📋 Planning max ${maxRequests} requests to complete ${provider.name}`);
    
    while (allGames.length < provider.totalGames) {
        requestCount++;
        const remainingGames = provider.totalGames - allGames.length;
        const gamesThisRequest = Math.min(CONFIG.GAMES_PER_REQUEST, remainingGames);
        
        console.log(`\n📥 Request ${requestCount} for ${provider.name}`);
        console.log(`📊 Current: ${allGames.length}/${provider.totalGames} games`);
        console.log(`📊 Fetching from offset: ${currentOffset}, limit: ${gamesThisRequest}`);
        
        let success = false;
        let attempt = 0;
        
        // Retry logic with proper offset management
        while (!success && attempt < CONFIG.MAX_RETRIES) {
            attempt++;
            console.log(`🔄 Attempt ${attempt}/${CONFIG.MAX_RETRIES}`);
            
            try {
                if (attempt > 1) {
                    console.log(`⏳ Waiting ${CONFIG.DELAY_BETWEEN_RETRIES/1000}s before retry...`);
                    await new Promise(resolve => setTimeout(resolve, CONFIG.DELAY_BETWEEN_RETRIES));
                }
                
                const result = await executeSingleRequest(provider.slug, currentOffset, gamesThisRequest);
                
                if (result.success && result.games && result.games.length > 0) {
                    // Filter out duplicate games (by ID)
                    const existingIds = new Set(allGames.map(g => g.id));
                    const newGames = result.games.filter(g => !existingIds.has(g.id));
                    
                    if (newGames.length > 0) {
                        allGames.push(...newGames);
                        currentOffset += result.games.length; // Move offset based on actual fetched count
                        
                        console.log(`✅ Added ${newGames.length} new games (Total: ${allGames.length}/${provider.totalGames})`);
                        
                        // Save checkpoint after each successful request
                        saveProviderData(provider, allGames, currentOffset);
                        
                        success = true;
                    } else {
                        console.log(`⚠️ No new games in response (all were duplicates)`);
                        currentOffset += CONFIG.GAMES_PER_REQUEST; // Still move offset forward
                        success = true; // Continue to next request
                    }
                } else {
                    throw new Error(`No games in response: ${result.error || 'Unknown error'}`);
                }
                
            } catch (error) {
                console.error(`❌ Attempt ${attempt} failed: ${error.message}`);
                if (attempt === CONFIG.MAX_RETRIES) {
                    console.log(`💥 All ${CONFIG.MAX_RETRIES} attempts failed, skipping to next offset`);
                    currentOffset += CONFIG.GAMES_PER_REQUEST; // Skip this offset
                    success = true; // Continue with next request
                }
            }
        }
        
        // Delay between requests
        if (allGames.length < provider.totalGames) {
            console.log(`⏳ Waiting ${CONFIG.DELAY_BETWEEN_REQUESTS/1000}s before next request...`);
            await new Promise(resolve => setTimeout(resolve, CONFIG.DELAY_BETWEEN_REQUESTS));
        }
        
        // Safety check to prevent infinite loops
        if (requestCount > maxRequests * 2) {
            console.log(`⚠️ Maximum request limit reached, stopping`);
            break;
        }
    }
    
    // Final save
    saveProviderData(provider, allGames, currentOffset);
    
    const isComplete = allGames.length >= provider.totalGames;
    console.log(`\n${isComplete ? '🎉' : '⚠️'} Provider ${provider.name} ${isComplete ? 'completed' : 'partially completed'}`);
    console.log(`📊 Final count: ${allGames.length}/${provider.totalGames} games`);
    
    return {
        success: true,
        provider: provider.name,
        totalGames: allGames.length,
        requestsMade: requestCount,
        isComplete: isComplete
    };
}

/**
 * Main function to complete all providers needing completion
 */
async function completeAllProviders() {
    console.log('🚀 Enhanced Provider Completion System');
    console.log('=====================================');
    
    // Scan all providers from checkpoints
    const allProviders = scanAllProviders();
    const incompleteProviders = allProviders.filter(p => p.needsCompletion);
    
    console.log(`\n📊 Found ${allProviders.length} total providers`);
    console.log(`📊 Found ${incompleteProviders.length} providers needing completion`);
    
    if (incompleteProviders.length === 0) {
        console.log('✅ All providers are already complete!');
        
        // Show complete providers
        const completeProviders = allProviders.filter(p => p.isComplete);
        console.log(`\n✅ Complete providers (${completeProviders.length}):`);
        completeProviders.forEach(p => {
            console.log(`   • ${p.name}: ${p.totalGames} games`);
        });
        
        return;
    }
    
    // Display incomplete providers
    console.log(`\n📋 Providers needing completion:`);
    incompleteProviders.forEach((p, i) => {
        console.log(`${i + 1}. ${p.name} - ${p.remainingGames} games remaining (${p.fetchedGames}/${p.totalGames})`);
    });
    
    // Process each provider one by one
    const results = [];
    for (let i = 0; i < incompleteProviders.length; i++) {
        const provider = incompleteProviders[i];
        
        try {
            const result = await completeProvider(provider);
            results.push(result);
            console.log(`✅ Completed ${result.provider}: ${result.totalGames} total games in ${result.requestsMade} requests`);
        } catch (error) {
            console.error(`❌ Failed to complete ${provider.name}: ${error.message}`);
            results.push({ success: false, provider: provider.name, error: error.message });
        }
        
        // Wait between providers
        if (i < incompleteProviders.length - 1) {
            console.log(`\n⏳ Waiting 10 seconds before next provider...`);
            await new Promise(resolve => setTimeout(resolve, 10000));
        }
    }
    
    // Final summary
    console.log('\n' + '='.repeat(80));
    console.log('🎉 Provider completion finished!');
    console.log('='.repeat(80));
    
    const successful = results.filter(r => r.success && r.isComplete);
    const partial = results.filter(r => r.success && !r.isComplete);
    const failed = results.filter(r => !r.success);
    
    console.log(`✅ Fully completed: ${successful.length} providers`);
    console.log(`⚠️ Partially completed: ${partial.length} providers`);
    console.log(`❌ Failed: ${failed.length} providers`);
    
    if (successful.length > 0) {
        console.log(`\n✅ Fully completed providers:`);
        successful.forEach(r => console.log(`   • ${r.provider}: ${r.totalGames} games`));
    }
    
    if (partial.length > 0) {
        console.log(`\n⚠️ Partially completed providers:`);
        partial.forEach(r => console.log(`   • ${r.provider}: ${r.totalGames} games`));
    }
    
    if (failed.length > 0) {
        console.log(`\n❌ Failed providers:`);
        failed.forEach(r => console.log(`   • ${r.provider}: ${r.error}`));
    }
}

// Run if called directly
if (require.main === module) {
    completeAllProviders().catch(error => {
        console.error('💥 Fatal error:', error.message);
        process.exit(1);
    });
}

module.exports = {
    scanAllProviders,
    completeProvider,
    completeAllProviders
};
