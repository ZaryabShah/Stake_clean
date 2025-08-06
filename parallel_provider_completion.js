// Enhanced Provider Completion with Parallel Processing
// Handles concurrent requests with robust offset management

const fs = require('fs');
const path = require('path');
const { parseStakeResponse } = require('./data_parser.js');

// Enhanced Configuration
const CONFIG = {
    GAMES_PER_REQUEST: 39,
    MAX_CONCURRENT_REQUESTS: 3, // Parallel requests
    MAX_RETRIES: 20, // Increased retries for more robust processing
    BASE_DELAY: 2000,
    RETRY_DELAY: 5000,
    PROVIDER_DELAY: 3000,
    DEBUG_MODE: true,
    SKIP_MISSING_GAMES: true, // Skip if games don't exist at offset
    MAX_EMPTY_ATTEMPTS: 10 // Stop after 10 consecutive empty responses
};

/**
 * Track offset status for parallel processing
 */
class OffsetTracker {
    constructor() {
        this.completed = new Set(); // Successfully fetched offsets
        this.failed = new Set(); // Failed offsets
        this.inProgress = new Set(); // Currently being fetched
        this.retryCount = new Map(); // Retry count per offset
    }

    markInProgress(offset) {
        this.inProgress.add(offset);
    }

    markCompleted(offset, gameCount) {
        this.inProgress.delete(offset);
        this.completed.add(offset);
        console.log(`✅ Offset ${offset} completed with ${gameCount} games`);
    }

    markFailed(offset) {
        this.inProgress.delete(offset);
        const retries = (this.retryCount.get(offset) || 0) + 1;
        this.retryCount.set(offset, retries);
        
        if (retries >= CONFIG.MAX_RETRIES) {
            this.failed.add(offset);
            console.log(`❌ Offset ${offset} permanently failed after ${retries} attempts`);
            return false; // Don't retry
        }
        
        console.log(`⚠️ Offset ${offset} failed (attempt ${retries}/${CONFIG.MAX_RETRIES})`);
        return true; // Can retry
    }

    isCompleted(offset) {
        return this.completed.has(offset);
    }

    isFailed(offset) {
        return this.failed.has(offset);
    }

    isInProgress(offset) {
        return this.inProgress.has(offset);
    }

    canFetch(offset) {
        return !this.isCompleted(offset) && !this.isFailed(offset) && !this.isInProgress(offset);
    }

    getNextOffsets(currentGames, totalGames, maxOffsets = CONFIG.MAX_CONCURRENT_REQUESTS) {
        const offsets = [];
        
        // First, check for failed offsets that can be retried
        for (const failedOffset of this.failed) {
            if (offsets.length >= maxOffsets) break;
            const retries = this.retryCount.get(failedOffset) || 0;
            if (retries < CONFIG.MAX_RETRIES && this.canFetch(failedOffset)) {
                // Remove from failed set to allow retry
                this.failed.delete(failedOffset);
                offsets.push(failedOffset);
            }
        }
        
        // Then, get new sequential offsets starting from where we have complete data
        let offset = this.getNextSequentialOffset();
        while (offsets.length < maxOffsets && offset < totalGames) {
            if (this.canFetch(offset)) {
                offsets.push(offset);
            }
            offset += CONFIG.GAMES_PER_REQUEST;
        }
        
        return offsets;
    }

    getNextSequentialOffset() {
        // Find the first offset that isn't completed
        let offset = 0;
        while (this.isCompleted(offset)) {
            offset += CONFIG.GAMES_PER_REQUEST;
        }
        return offset;
    }

    getStatus() {
        return {
            completed: Array.from(this.completed).sort((a, b) => a - b),
            failed: Array.from(this.failed).sort((a, b) => a - b),
            inProgress: Array.from(this.inProgress).sort((a, b) => a - b)
        };
    }
}

/**
 * Execute a single GraphQL request with enhanced error handling
 */
async function executeSingleRequest(providerSlug, offset, limit, requestId) {
    const { spawn } = require('child_process');
    
    return new Promise((resolve, reject) => {
        console.log(`🚀 [${requestId}] Executing: node ./simple_fetcher.js ${providerSlug} ${offset} ${limit}`);
        
        const process = spawn('node', ['./simple_fetcher.js', providerSlug, offset.toString(), limit.toString()], {
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
                // Find the most recent raw response file for this provider
                const files = fs.readdirSync('./')
                    .filter(f => f.startsWith('stake_raw_response_') && f.includes(providerSlug) && f.endsWith('.txt'))
                    .sort()
                    .reverse();
                
                if (files.length > 0) {
                    const responseFile = files[0];
                    
                    try {
                        const responseData = fs.readFileSync(responseFile, 'utf8');
                        const parsed = parseStakeResponse(responseData);
                        
                        resolve({
                            success: parsed.success,
                            games: parsed.games || [],
                            error: parsed.error,
                            responseFile
                        });
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
            process.kill();
            reject(new Error('Request timeout'));
        }, 90000); // 90 seconds timeout
    });
}

/**
 * Enhanced provider completion with parallel processing and proper retry logic
 */
async function completeProviderParallel(provider) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`🎯 Starting parallel completion for: ${provider.name}`);
    console.log(`📊 Total: ${provider.totalGames}, Fetched: ${provider.fetchedGames}, Remaining: ${provider.remainingGames}`);
    console.log(`📁 Output directory: ${provider.outputDir}`);
    console.log(`${'='.repeat(80)}`);
    
    // Load existing games and organize by offset
    const gamesByOffset = new Map();
    const gamesFile = path.join(provider.outputDir, 'initial_games.json');
    
    if (fs.existsSync(gamesFile)) {
        try {
            const data = JSON.parse(fs.readFileSync(gamesFile, 'utf8'));
            const existingGames = data.games || [];
            
            // Organize existing games by offset (assuming they're in order)
            for (let i = 0; i < existingGames.length; i += CONFIG.GAMES_PER_REQUEST) {
                const offset = i;
                const offsetGames = existingGames.slice(i, i + CONFIG.GAMES_PER_REQUEST);
                gamesByOffset.set(offset, offsetGames);
            }
        } catch (error) {
            console.log(`⚠️ Could not load existing games: ${error.message}`);
        }
    }
    
    console.log(`📚 Loaded games for ${gamesByOffset.size} offsets`);
    
    // Calculate total existing games
    let totalExistingGames = 0;
    for (const games of gamesByOffset.values()) {
        totalExistingGames += games.length;
    }
    
    // Check if already complete
    if (totalExistingGames >= provider.totalGames) {
        console.log(`✅ Provider ${provider.name} is already complete! (${totalExistingGames}/${provider.totalGames})`);
        return {
            success: true,
            provider: provider.name,
            totalGames: totalExistingGames,
            requestsMade: 0,
            isComplete: true
        };
    }
    
    const tracker = new OffsetTracker();
    let requestCount = 0;
    let emptyResponseCount = 0;
    
    // Load existing checkpoint data to restore failed offsets
    const checkpointFile = path.join('checkpoints', `provider_${provider.slug}_initial.json`);
    if (fs.existsSync(checkpointFile)) {
        try {
            const checkpointData = JSON.parse(fs.readFileSync(checkpointFile, 'utf8'));
            
            // Restore failed offsets and retry counts
            if (checkpointData.failed_offsets) {
                checkpointData.failed_offsets.forEach(offset => tracker.failed.add(offset));
            }
            if (checkpointData.retry_counts) {
                Object.entries(checkpointData.retry_counts).forEach(([offset, count]) => {
                    tracker.retryCount.set(parseInt(offset), count);
                });
            }
            
            console.log(`📋 Restored ${checkpointData.failed_offsets?.length || 0} failed offsets from checkpoint`);
        } catch (error) {
            console.log(`⚠️ Could not load checkpoint data: ${error.message}`);
        }
    }
    
    // Mark existing offsets as completed
    for (const [offset, games] of gamesByOffset.entries()) {
        tracker.markCompleted(offset, games.length);
    }
    
    console.log(`📋 Starting parallel requests from missing offsets`);
    console.log(`📋 Max concurrent requests: ${CONFIG.MAX_CONCURRENT_REQUESTS}`);
    
    while (totalExistingGames < provider.totalGames && emptyResponseCount < CONFIG.MAX_EMPTY_ATTEMPTS) {
        // Check if too many offsets have permanently failed (skip provider)
        if (tracker.failed.size >= 3) {
            console.log(`🚫 Too many permanent failures (${tracker.failed.size}), skipping provider`);
            break;
        }
        
        // Get next offsets to fetch (including retries for failed offsets)
        const offsets = tracker.getNextOffsets(totalExistingGames, provider.totalGames);
        
        if (offsets.length === 0) {
            // Check if we have any failed offsets that can still be retried
            const hasRetryableFailures = Array.from(tracker.failed).some(offset => {
                const retries = tracker.retryCount.get(offset) || 0;
                return retries < CONFIG.MAX_RETRIES;
            });
            
            if (hasRetryableFailures) {
                console.log(`⏸️ Waiting for retryable failures...`);
                await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY));
                continue;
            } else if (tracker.inProgress.size > 0) {
                console.log(`⏸️ No more offsets to fetch, waiting for in-progress requests...`);
                await new Promise(resolve => setTimeout(resolve, 2000));
                continue;
            } else {
                console.log(`⏹️ No more requests possible, ending collection...`);
                break;
            }
        }
        
        console.log(`\n📥 Starting ${offsets.length} parallel requests: ${offsets.join(', ')}`);
        
        // Show which requests are retries
        offsets.forEach(offset => {
            const retries = tracker.retryCount.get(offset) || 0;
            if (retries > 0) {
                console.log(`🔄 Offset ${offset} is a retry (attempt ${retries + 1}/${CONFIG.MAX_RETRIES})`);
            }
        });
        
        // Mark offsets as in progress
        offsets.forEach(offset => tracker.markInProgress(offset));
        
        // Create parallel requests
        const requests = offsets.map(async (offset) => {
            const limit = Math.min(CONFIG.GAMES_PER_REQUEST, provider.totalGames - offset);
            const requestId = `R${++requestCount}`;
            
            try {
                const result = await executeSingleRequest(provider.slug, offset, limit, requestId);
                
                if (result.success && result.games.length > 0) {
                    tracker.markCompleted(offset, result.games.length);
                    return { offset, games: result.games, success: true };
                } else {
                    // Empty response - might be end of data
                    console.log(`⚠️ [${requestId}] Empty response at offset ${offset}`);
                    emptyResponseCount++;
                    
                    if (CONFIG.SKIP_MISSING_GAMES) {
                        tracker.markCompleted(offset, 0); // Mark as completed but with 0 games
                        return { offset, games: [], success: true };
                    } else {
                        tracker.markFailed(offset);
                        return { offset, games: [], success: false };
                    }
                }
            } catch (error) {
                console.log(`❌ [${requestId}] Request failed: ${error.message}`);
                const canRetry = tracker.markFailed(offset);
                return { offset, games: [], success: false, canRetry };
            }
        });
        
        // Wait for all parallel requests to complete
        const results = await Promise.allSettled(requests);
        
        // Process results and update gamesByOffset map
        let newGamesAdded = 0;
        
        results.forEach((result, index) => {
            const offset = offsets[index];
            if (result.status === 'fulfilled') {
                const requestResult = result.value;
                if (requestResult.success && requestResult.games.length > 0) {
                    gamesByOffset.set(offset, requestResult.games);
                    newGamesAdded += requestResult.games.length;
                    emptyResponseCount = 0; // Reset empty count on successful fetch
                }
            }
        });
        
        if (newGamesAdded > 0) {
            // Recalculate total games
            totalExistingGames = 0;
            for (const games of gamesByOffset.values()) {
                totalExistingGames += games.length;
            }
            
            console.log(`✅ Added ${newGamesAdded} new games (Total: ${totalExistingGames}/${provider.totalGames})`);
            
            // Convert map to sequential array for saving
            const allGames = [];
            const sortedOffsets = Array.from(gamesByOffset.keys()).sort((a, b) => a - b);
            for (const offset of sortedOffsets) {
                allGames.push(...gamesByOffset.get(offset));
            }
            
            // Save progress
            saveProviderData(provider, allGames, tracker);
            
            // Check if complete
            if (totalExistingGames >= provider.totalGames) {
                console.log(`🎉 Provider ${provider.name} completed!`);
                break;
            }
        }
        
        // Show tracker status
        const status = tracker.getStatus();
        console.log(`📊 Tracker: ${status.completed.length} completed, ${status.failed.length} failed, ${status.inProgress.length} in progress`);
        
        // Small delay between batches
        await new Promise(resolve => setTimeout(resolve, CONFIG.BASE_DELAY));
    }
    
    // Final save with all games in order
    const finalGames = [];
    const sortedOffsets = Array.from(gamesByOffset.keys()).sort((a, b) => a - b);
    for (const offset of sortedOffsets) {
        finalGames.push(...gamesByOffset.get(offset));
    }
    saveProviderData(provider, finalGames, tracker);
    
    return {
        success: true,
        provider: provider.name,
        totalGames: finalGames.length,
        requestsMade: requestCount,
        isComplete: finalGames.length >= provider.totalGames
    };
}

/**
 * Save provider data to files
 */
function saveProviderData(provider, allGames, tracker) {
    try {
        // Check if tracker is defined
        if (!tracker) {
            console.error('❌ Tracker parameter is undefined in saveProviderData');
            return false;
        }
        
        // Ensure output directory exists
        if (!fs.existsSync(provider.outputDir)) {
            fs.mkdirSync(provider.outputDir, { recursive: true });
        }
        
        const gamesFile = path.join(provider.outputDir, 'initial_games.json');
        const checkpointFile = path.join('checkpoints', `provider_${provider.slug}_initial.json`);
        
        // Save games data
        const gamesData = {
            timestamp: new Date().toISOString(),
            provider_slug: provider.slug,
            provider_name: provider.name,
            total_games: provider.totalGames,
            games_fetched: allGames.length,
            games: allGames
        };
        
        fs.writeFileSync(gamesFile, JSON.stringify(gamesData, null, 2));
        
        // Update checkpoint with offset tracking
        const status = tracker.getStatus();
        const checkpointData = {
            timestamp: new Date().toISOString(),
            provider_slug: provider.slug,
            provider_name: provider.name,
            status: allGames.length >= provider.totalGames ? "completed" : "in_progress",
            total_games: provider.totalGames,
            games_fetched: allGames.length,
            is_complete: allGames.length >= provider.totalGames,
            needs_pagination: allGames.length < provider.totalGames,
            output_dir: provider.outputDir,
            games_data_file: gamesFile,
            source: "parallel_graphql_fetch",
            completed_offsets: status.completed,
            failed_offsets: status.failed,
            retry_counts: Object.fromEntries(tracker.retryCount),
            last_successful_offset: Math.max(...status.completed, -1)
        };
        
        fs.writeFileSync(checkpointFile, JSON.stringify(checkpointData, null, 2));
        console.log(`💾 Saved ${allGames.length} games to: ${gamesFile}`);
        console.log(`💾 Updated checkpoint: ${checkpointFile}`);
        
        return true;
    } catch (error) {
        console.error(`❌ Save error: ${error.message}`);
        return false;
    }
}

// Export functions for use in other scripts
module.exports = {
    completeProviderParallel,
    CONFIG
};

// Test if run directly
if (require.main === module) {
    const testProvider = {
        name: 'Test Provider',
        slug: 'test-provider',
        totalGames: 100,
        fetchedGames: 39,
        remainingGames: 61,
        outputDir: 'stake_thumbnails/Test_Provider'
    };
    
    completeProviderParallel(testProvider)
        .then(result => console.log('Test Result:', result))
        .catch(error => console.error('Test Error:', error.message));
}
