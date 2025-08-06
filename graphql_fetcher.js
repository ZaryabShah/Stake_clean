// GraphQL API fetcher for Stake.com provider data - FIXED VERSION
const Scrappey = require('scrappey-wrapper');
const fs = require('fs');

// Initialize Scrappey with your API key
const scrappey = new Scrappey('CPLgrNtC9kgMlgvBpMLydXJU3wIYVhD9bvxKn0ZO8SRWPNJvpgu4Ezhwki1U');

// GraphQL query and variables
const graphqlPayload = {
    query: `query SlugKuratorGroup($slug: String!, $limit: Int!, $offset: Int!, $showGames: Boolean = true, $sort: GameKuratorGroupGameSortEnum = popular, $showProviders: Boolean = false, $filterIds: [String!], $isActivePlayersFeatureFlagOn: Boolean = false, $language: LanguageEnum = en) {
  slugKuratorGroup(slug: $slug) {
    ...GameKuratorGroup
    gameCount(filterIds: $filterIds, language: $language)
    groupGamesList(
      limit: $limit
      offset: $offset
      sort: $sort
      filterIds: $filterIds
      language: $language
    ) @include(if: $showGames) {
      ...GameKuratorGroupGame
      game {
        playerCount @include(if: $isActivePlayersFeatureFlagOn)
      }
    }
    filtersProvider: filters(type: provider) @include(if: $showProviders) {
      count
      group {
        id
        translation
        gameCount
      }
    }
  }
}

fragment GameKuratorGroup on GameKuratorGroup {
  id
  slug
  translation
  icon
  type
}

fragment GameKuratorGroupGame on GameKuratorGroupGame {
  id
  game {
    ...GameCardKuratorGame
  }
}

fragment GameCardKuratorGame on GameKuratorGame {
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
}`,
    variables: {
        slug: "pragmatic-play",
        sort: "userCount",
        filterIds: null,
        limit: 39,
        isActivePlayersFeatureFlagOn: true,
        offset: 39
    }
};

async function fetchProviderDataGraphQL(providerSlug = "pragmatic-play", limit = 39, offset = 39) {
    const maxRetries = 3;
    const retryDelay = 3000; // 3 seconds
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`🚀 Fetching ${providerSlug} data via GraphQL API (attempt ${attempt}/${maxRetries})...`);
            
            // Create session with residential proxy (US)
            const session = await scrappey.createSession({
                proxy: {
                    country: 'US'
                }
            });
            
            console.log('✅ Session created successfully:', session.session);
            
            // Update variables with user input
            const payload = {
                ...graphqlPayload,
                variables: {
                    ...graphqlPayload.variables,
                    slug: providerSlug,
                    limit: limit,
                    offset: offset
                }
            };
            
            // Make POST request to GraphQL API
            const response = await scrappey.post({
                url: 'https://stake.com/_api/graphql',
                session: session.session,
                postData: JSON.stringify(payload),
                customHeaders: {
                    'Content-Type': 'application/json',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Origin': 'https://stake.com',
                    'Referer': `https://stake.com/casino/group/${providerSlug}`,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                    'x-language': 'en',
                    'x-operation-name': 'SlugKuratorGroup',
                    'x-operation-type': 'query'
                }
            });
            
            console.log('✅ GraphQL request successful');
            console.log('📊 Response status:', response.status);
            
            // Check the actual response structure and log for debugging
            console.log('📋 Full response structure:', Object.keys(response));
            
            let responseData;
            if (response.solution && response.solution.response) {
                responseData = response.solution.response;
            } else if (response.response) {
                responseData = response.response;
            } else if (response.data) {
                responseData = response.data;
            } else if (response.content) {
                responseData = response.content;
            } else {
                console.log('❌ Could not find response data in any expected field');
                console.log('📋 Available keys:', Object.keys(response));
                throw new Error('Could not find response data');
            }
            
            console.log('📊 Response data type:', typeof responseData);
            
            // Parse JSON response with ENHANCED error handling
            let jsonData;
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            
            // Always save raw response for debugging
            const rawFilename = `stake_raw_response_${providerSlug}_${timestamp}.txt`;
            fs.writeFileSync(rawFilename, String(responseData));
            console.log(`💾 Raw response saved to: ${rawFilename}`);
            
            if (typeof responseData === 'string') {
                // Check if response is wrapped in HTML
                if (responseData.includes('<div id="resultContainer">') || responseData.includes('<div>')) {
                    console.log('🔧 Extracting JSON from HTML wrapper...');
                    
                    // Enhanced extraction patterns
                    let jsonString = null;
                    
                    // Pattern 1: Specific result container
                    let match = responseData.match(/<div[^>]*id="resultContainer"[^>]*><div[^>]*>({.*?})<\/div>/s);
                    if (match && match[1]) {
                        jsonString = match[1];
                        console.log('✅ Found JSON in resultContainer');
                    } else {
                        // Pattern 2: Any div with JSON
                        match = responseData.match(/<div[^>]*>({.*?})<\/div>/s);
                        if (match && match[1]) {
                            jsonString = match[1];
                            console.log('✅ Found JSON in generic div');
                        } else {
                            // Pattern 3: Extract the largest JSON object
                            const jsonMatches = responseData.match(/\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g);
                            if (jsonMatches && jsonMatches.length > 0) {
                                // Take the largest JSON string (most likely to be complete)
                                jsonString = jsonMatches.reduce((a, b) => a.length > b.length ? a : b);
                                console.log('✅ Found JSON using pattern matching');
                            } else {
                                // Pattern 4: Extract everything between first { and last }
                                const firstBrace = responseData.indexOf('{');
                                const lastBrace = responseData.lastIndexOf('}');
                                if (firstBrace !== -1 && lastBrace !== -1 && firstBrace < lastBrace) {
                                    jsonString = responseData.substring(firstBrace, lastBrace + 1);
                                    console.log('✅ Found JSON using brace extraction');
                                }
                            }
                        }
                    }
                    
                    if (jsonString) {
                        // Clean up the JSON string
                        jsonString = jsonString.trim();
                        
                        // Handle truncated JSON by ensuring balanced braces
                        if (!jsonString.endsWith('}')) {
                            let braceCount = 0;
                            let lastValidPos = -1;
                            
                            for (let i = 0; i < jsonString.length; i++) {
                                if (jsonString[i] === '{') {
                                    braceCount++;
                                } else if (jsonString[i] === '}') {
                                    braceCount--;
                                    if (braceCount === 0) {
                                        lastValidPos = i;
                                    }
                                }
                            }
                            
                            if (lastValidPos > 0) {
                                jsonString = jsonString.substring(0, lastValidPos + 1);
                                console.log('🔧 Truncated JSON to last valid position');
                            }
                        }
                        
                        console.log('📄 JSON preview:', jsonString.substring(0, 300) + '...');
                        
                        try {
                            jsonData = JSON.parse(jsonString);
                            console.log('✅ Successfully parsed extracted JSON');
                        } catch (parseError) {
                            console.log('❌ Failed to parse extracted JSON:', parseError.message);
                            
                            // Try to fix common JSON issues
                            let fixedJson = jsonString
                                .replace(/,\s*}/g, '}')  // Remove trailing commas
                                .replace(/,\s*]/g, ']')   // Remove trailing commas in arrays
                                .replace(/([{,]\s*)(\w+):/g, '$1"$2":'); // Quote unquoted keys
                            
                            try {
                                jsonData = JSON.parse(fixedJson);
                                console.log('✅ Successfully parsed fixed JSON');
                            } catch (fixError) {
                                console.log('❌ Failed to parse even after fixes:', fixError.message);
                                throw new Error(`Could not parse JSON: ${parseError.message}`);
                            }
                        }
                    } else {
                        console.log('❌ Could not extract JSON from HTML wrapper');
                        throw new Error('Could not extract JSON from HTML wrapper');
                    }
                } else if (responseData.trim().startsWith('{') || responseData.trim().startsWith('[')) {
                    // Direct JSON response
                    try {
                        jsonData = JSON.parse(responseData);
                        console.log('✅ Successfully parsed direct JSON');
                    } catch (parseError) {
                        console.log('❌ Failed to parse direct JSON:', parseError.message);
                        throw new Error(`Failed to parse direct JSON: ${parseError.message}`);
                    }
                } else {
                    console.log('❌ Response is not JSON format');
                    console.log('📄 Response preview:', responseData.substring(0, 500));
                    throw new Error('Response is not valid JSON format');
                }
            } else {
                jsonData = responseData;
                console.log('✅ Using response data as-is');
            }
            
            console.log('📏 Response data keys:', Object.keys(jsonData));
            
            // Generate timestamp for filename
            const finalTimestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const filename = `stake_${providerSlug}_graphql_${finalTimestamp}.json`;
            
            // Save the JSON response
            fs.writeFileSync(filename, JSON.stringify(jsonData, null, 2));
            console.log(`💾 GraphQL response saved to: ${filename}`);
            
            // Analyze the GraphQL response
            analyzeGraphQLResponse(jsonData, providerSlug);
            
            // Also save as latest.json for easy access
            fs.writeFileSync(`stake_${providerSlug}_latest.json`, JSON.stringify(jsonData, null, 2));
            console.log(`💾 Also saved as: stake_${providerSlug}_latest.json`);
            
            // Destroy session to clean up
            await scrappey.destroySession(session.session);
            console.log('🧹 Session cleaned up');
            
            console.log(`🎉 Successfully fetched ${providerSlug} GraphQL data!`);
            return jsonData;
            
        } catch (error) {
            console.error(`❌ Error on attempt ${attempt} for ${providerSlug}:`, error.message);
            
            if (attempt < maxRetries) {
                const waitTime = retryDelay * attempt;
                console.log(`⏳ Retrying GraphQL request in ${waitTime / 1000} seconds...`);
                await new Promise(resolve => setTimeout(resolve, waitTime));
            } else {
                console.error(`💥 All ${maxRetries} GraphQL attempts failed for ${providerSlug}`);
                throw error;
            }
        }
    }
}

function analyzeGraphQLResponse(jsonData, providerSlug) {
    try {
        console.log('\n📊 Analyzing GraphQL response...');
        
        if (jsonData.data && jsonData.data.slugKuratorGroup) {
            const group = jsonData.data.slugKuratorGroup;
            
            console.log(`🏢 Provider: ${group.translation || group.slug}`);
            console.log(`🎮 Total games: ${group.gameCount || 'Unknown'}`);
            console.log(`🆔 Group ID: ${group.id}`);
            console.log(`🔗 Slug: ${group.slug}`);
            console.log(`📂 Type: ${group.type}`);
            
            if (group.groupGamesList && group.groupGamesList.length > 0) {
                console.log(`\n🎯 Found ${group.groupGamesList.length} games in this batch:`);
                
                group.groupGamesList.forEach((gameItem, index) => {
                    const game = gameItem.game;
                    console.log(`  ${index + 1}. ${game.name} (${game.slug})`);
                    if (game.playerCount !== undefined) {
                        console.log(`     👥 Players: ${game.playerCount}`);
                    }
                });
            }
            
            if (group.filtersProvider && group.filtersProvider.group) {
                console.log(`\n🏭 Available providers: ${group.filtersProvider.group.length}`);
                group.filtersProvider.group.forEach((provider, index) => {
                    console.log(`  ${index + 1}. ${provider.translation} (${provider.gameCount} games)`);
                });
            }
        } else if (jsonData.errors) {
            console.log('❌ GraphQL errors found:');
            jsonData.errors.forEach((error, index) => {
                console.log(`  ${index + 1}. ${error.message}`);
            });
        } else {
            console.log('⚠️ Unexpected response structure');
            console.log('📋 Available keys:', Object.keys(jsonData));
        }
        
        console.log(`\n🎉 Successfully analyzed ${providerSlug} GraphQL response!`);
        
    } catch (error) {
        console.log('⚠️ Error analyzing response:', error.message);
    }
}

// Function to fetch all providers
async function fetchAllProviders() {
    const commonProviders = [
        'pragmatic-play',
        'evolution',
        'netent',
        'play-n-go',
        'microgaming',
        'big-time-gaming',
        'yggdrasil',
        'red-tiger',
        'push-gaming',
        'hacksaw-gaming'
    ];
    
    console.log('🚀 Fetching data for all major providers...');
    
    for (const provider of commonProviders) {
        try {
            console.log(`\n⏳ Processing ${provider}...`);
            await fetchProviderDataGraphQL(provider, 50, 0);
            
            // Wait a bit between requests to be respectful
            await new Promise(resolve => setTimeout(resolve, 2000));
            
        } catch (error) {
            console.error(`❌ Failed to fetch ${provider}:`, error.message);
            continue;
        }
    }
    
    console.log('\n🎉 Finished fetching all providers!');
}

// Function for continuous monitoring
async function continuousMonitoring(providerSlug, intervalMinutes = 30) {
    console.log(`🔄 Starting continuous monitoring for ${providerSlug} every ${intervalMinutes} minutes...`);
    
    // Fetch immediately on start
    await fetchProviderDataGraphQL(providerSlug);
    
    // Set up interval for continuous fetching
    setInterval(async () => {
        console.log(`\n⏰ Scheduled fetch for ${providerSlug} starting...`);
        try {
            await fetchProviderDataGraphQL(providerSlug);
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
    const limitArg = args.find(arg => arg.startsWith('--limit='));
    const offsetArg = args.find(arg => arg.startsWith('--offset='));
    const intervalArg = args.find(arg => arg.startsWith('--interval='));
    
    const provider = providerArg ? providerArg.split('=')[1] : 'pragmatic-play';
    const limit = limitArg ? parseInt(limitArg.split('=')[1]) : 39;
    const offset = offsetArg ? parseInt(offsetArg.split('=')[1]) : 0;
    const interval = intervalArg ? parseInt(intervalArg.split('=')[1]) : 30;
    
    if (args.includes('--all')) {
        // Fetch all providers
        await fetchAllProviders();
    } else if (args.includes('--continuous') || args.includes('-c')) {
        // Continuous monitoring
        await continuousMonitoring(provider, interval);
    } else {
        // Single fetch
        await fetchProviderDataGraphQL(provider, limit, offset);
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

module.exports = { fetchProviderDataGraphQL, fetchAllProviders, continuousMonitoring };
