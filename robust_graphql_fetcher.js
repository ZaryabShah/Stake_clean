// Enhanced GraphQL fetcher for Stake.com with environment variable support
const Scrappey = require('scrappey-wrapper');
const fs = require('fs');

// Initialize Scrappey with your API key
const scrappey = new Scrappey('CPLgrNtC9kgMlgvBpMLydXJU3wIYVhD9bvxKn0ZO8SRWPNJvpgu4Ezhwki1U');

// Get configuration from environment variables
const PROVIDER_SLUG = process.env.PROVIDER_SLUG || 'stake-originals';
const PROVIDER_NAME = process.env.PROVIDER_NAME || 'Stake Originals';
const OUTPUT_DIR = process.env.OUTPUT_DIR || './output';
const GAMES_LIMIT = parseInt(process.env.GAMES_LIMIT) || 39;
const GAMES_OFFSET = parseInt(process.env.GAMES_OFFSET) || 0;

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

function validateGraphQLResponse(response) {
    try {
        // Check if response has the expected structure
        if (!response || typeof response !== 'object') {
            console.log('❌ Invalid response structure');
            return false;
        }

        // Check for GraphQL data
        if (!response.data || !response.data.slugKuratorGroup) {
            console.log('❌ Missing GraphQL data structure');
            return false;
        }

        // Check for games list
        if (!response.data.slugKuratorGroup.groupGamesList || !Array.isArray(response.data.slugKuratorGroup.groupGamesList)) {
            console.log('❌ Missing or invalid games list');
            return false;
        }

        const gamesList = response.data.slugKuratorGroup.groupGamesList;
        console.log(`✅ GraphQL response validated: ${gamesList.length} games found`);
        return true;

    } catch (error) {
        console.log('❌ GraphQL validation error:', error.message);
        return false;
    }
}

function extractGameData(gamesList) {
    const games = [];
    
    for (const item of gamesList) {
        try {
            if (!item.game) continue;
            
            const game = item.game;
            
            // Extract provider from groupGames
            let provider = PROVIDER_NAME;
            let providerSlug = PROVIDER_SLUG;
            
            if (game.groupGames && Array.isArray(game.groupGames)) {
                for (const group of game.groupGames) {
                    if (group.group && group.group.type === 'provider') {
                        provider = group.group.translation || provider;
                        providerSlug = group.group.slug || providerSlug;
                        break;
                    }
                }
            }
            
            // Extract categories and themes
            const categories = [];
            const themes = [];
            
            if (game.groupGames && Array.isArray(game.groupGames)) {
                for (const group of game.groupGames) {
                    if (group.group) {
                        if (group.group.type === 'category') {
                            categories.push(group.group.translation);
                        } else if (group.group.type === 'theme') {
                            themes.push(group.group.translation);
                        }
                    }
                }
            }
            
            const gameData = {
                game_id: game.id,
                title: game.name,
                slug: game.slug,
                provider: provider,
                provider_slug: providerSlug,
                thumbnail_url: game.thumbnailUrl,
                thumbnail_blur_hash: game.thumbnailBlurHash || null,
                player_count: game.playerCount || 0,
                is_blocked: game.isBlocked || false,
                is_widget_enabled: game.isWidgetEnabled || true,
                categories: categories,
                themes: themes
            };
            
            games.push(gameData);
            
        } catch (error) {
            console.log('⚠️ Error extracting game data:', error.message);
        }
    }
    
    return games;
}

async function fetchGamesWithGraphQL(providerSlug, limit = 39, offset = 0, maxRetries = 3) {
    let session = null;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`🚀 Fetching games for ${providerSlug} (Attempt ${attempt}/${maxRetries})`);
            console.log(`📊 Limit: ${limit}, Offset: ${offset}`);
            
            // Create session with residential proxy
            session = await scrappey.createSession({
                proxy: {
                    country: 'US'
                }
            });
            
            console.log('✅ Session created successfully:', session.session);
            
            // GraphQL query for games
            const graphqlQuery = {
                query: `
                    query SlugKuratorGroup($slug: String!, $first: Int!, $after: String) {
                        slugKuratorGroup(slug: $slug) {
                            groupGamesList(first: $first, after: $after) {
                                id
                                game {
                                    id
                                    name
                                    slug
                                    thumbnailUrl
                                    thumbnailBlurHash
                                    isBlocked
                                    isWidgetEnabled
                                    groupGames {
                                        group {
                                            translation
                                            type
                                            id
                                            slug
                                        }
                                    }
                                    playerCount
                                }
                            }
                        }
                    }
                `,
                variables: {
                    slug: providerSlug,
                    first: limit,
                    after: offset > 0 ? btoa(`arrayconnection:${offset - 1}`) : null
                }
            };
            
            // Make GraphQL request
            const response = await scrappey.post({
                url: 'https://stake.com/api/graphql',
                session: session.session,
                postData: JSON.stringify(graphqlQuery),
                customHeaders: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Origin': 'https://stake.com',
                    'Referer': `https://stake.com/casino/group/${providerSlug}`
                }
            });
            
            console.log('✅ GraphQL request completed');
            console.log('📊 Response status:', response.status);
            
            // Extract response content
            let responseContent;
            if (response.solution && response.solution.response) {
                responseContent = response.solution.response;
            } else if (response.response) {
                responseContent = response.response;
            } else {
                throw new Error('No response content found');
            }
            
            // Parse JSON response
            let jsonResponse;
            try {
                jsonResponse = JSON.parse(responseContent);
            } catch (parseError) {
                console.log('❌ Failed to parse JSON response');
                throw parseError;
            }
            
            // Validate GraphQL response
            if (!validateGraphQLResponse(jsonResponse)) {
                throw new Error('Invalid GraphQL response structure');
            }
            
            // Extract games data
            const gamesList = jsonResponse.data.slugKuratorGroup.groupGamesList;
            const extractedGames = extractGameData(gamesList);
            
            console.log(`🎮 Successfully extracted ${extractedGames.length} games`);
            
            // Calculate total games (this is an approximation)
            const totalGames = gamesList.length < limit ? offset + gamesList.length : offset + limit + 1;
            
            // Save the raw GraphQL response
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const rawResponseFile = `${OUTPUT_DIR}/${providerSlug}_graphql_${timestamp}.json`;
            fs.writeFileSync(rawResponseFile, JSON.stringify(jsonResponse, null, 2));
            console.log(`💾 Raw GraphQL response saved: ${rawResponseFile}`);
            
            // Save extracted games data
            const gamesFile = `${OUTPUT_DIR}/${providerSlug}_games_${timestamp}.json`;
            const gamesData = {
                timestamp: new Date().toISOString(),
                provider_slug: providerSlug,
                provider_name: PROVIDER_NAME,
                games_count: extractedGames.length,
                offset: offset,
                limit: limit,
                total_games: totalGames,
                games: extractedGames
            };
            
            fs.writeFileSync(gamesFile, JSON.stringify(gamesData, null, 2));
            console.log(`💾 Games data saved: ${gamesFile}`);
            
            // Output statistics for the Python script
            console.log(`Total games: ${totalGames}`);
            console.log(`Games fetched: ${extractedGames.length}`);
            console.log(`Offset: ${offset}`);
            
            // Destroy session
            try {
                if (session) {
                    await scrappey.destroySession(session.session);
                    console.log('🧹 Session cleaned up successfully');
                }
            } catch (cleanupError) {
                console.log('⚠️ Session cleanup failed (non-fatal):', cleanupError.message);
            }
            
            return {
                success: true,
                games: extractedGames,
                total_games: totalGames,
                games_fetched: extractedGames.length
            };
            
        } catch (error) {
            console.error(`❌ Attempt ${attempt} failed:`, error.message);
            
            // Cleanup session on error
            if (session) {
                try {
                    await scrappey.destroySession(session.session);
                    console.log('🧹 Session cleaned up after error');
                } catch (cleanupError) {
                    console.log('⚠️ Session cleanup failed:', cleanupError.message);
                }
                session = null;
            }
            
            // If this was the last attempt, throw the error
            if (attempt === maxRetries) {
                throw error;
            }
            
            // Wait before retry
            const waitTime = Math.pow(2, attempt) * 3000;
            console.log(`⏳ Waiting ${waitTime/1000}s before retry...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }
    }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Gracefully shutting down...');
    process.exit(0);
});

// Main execution
async function main() {
    try {
        console.log(`🎯 Starting GraphQL fetch for provider: ${PROVIDER_NAME}`);
        console.log(`📊 Provider slug: ${PROVIDER_SLUG}`);
        console.log(`📊 Games limit: ${GAMES_LIMIT}`);
        console.log(`📊 Games offset: ${GAMES_OFFSET}`);
        console.log(`📁 Output directory: ${OUTPUT_DIR}`);
        
        const result = await fetchGamesWithGraphQL(PROVIDER_SLUG, GAMES_LIMIT, GAMES_OFFSET);
        
        if (result.success) {
            console.log('🎉 GraphQL fetch completed successfully!');
            process.exit(0);
        } else {
            console.log('❌ GraphQL fetch failed');
            process.exit(1);
        }
        
    } catch (error) {
        console.error('💥 Fatal error:', error.message);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
}

module.exports = { fetchGamesWithGraphQL };
