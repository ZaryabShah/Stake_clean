// Data Parser for Stake.com GraphQL responses
// Extracts essential game data from JSON/HTML responses

const fs = require('fs');

/**
 * Parse GraphQL response and extract game data
 * @param {string} responseData - Raw response (HTML or JSON)
 * @returns {Object} Parsed data with games array and metadata
 */
function parseStakeResponse(responseData) {
    try {
        let jsonData = null;
        
        // Check if response is just an error string or too short to be valid
        const trimmedResponse = responseData.trim();
        if (trimmedResponse === 'error' || trimmedResponse.length < 50) {
            console.log(`❌ Response is invalid: "${trimmedResponse}" (length: ${trimmedResponse.length})`);
            return {
                success: false,
                error: `API returned invalid response: "${trimmedResponse}"`,
                metadata: null,
                games: [],
                remainingGames: 0
            };
        }
        
        // Check if response is HTML wrapped
        if (responseData.includes('<div id="resultContainer">') || responseData.includes('<div>')) {
            console.log('📦 Extracting JSON from HTML wrapper...');
            
            // Try regex-based extraction first for robustness
            return parseWithRegex(responseData);
            
        } else {
            // Try to parse as direct JSON
            jsonData = JSON.parse(responseData);
            console.log('✅ Successfully parsed direct JSON');
            return extractDataFromJson(jsonData);
        }
        
    } catch (error) {
        console.error('❌ Parse error:', error.message);
        return {
            success: false,
            error: error.message,
            metadata: null,
            games: [],
            remainingGames: 0
        };
    }
}

/**
 * Parse using regex extraction for robustness
 * @param {string} responseData - HTML response
 * @returns {Object} Parsed data
 */
function parseWithRegex(responseData) {
    try {
        console.log('🔍 Using regex-based parsing for robustness...');
        
        // First try to extract complete JSON from resultContainer
        const resultContainerMatch = responseData.match(/<div[^>]*id="resultContainer"[^>]*><div[^>]*>(\{.*?\})<\/div>/s);
        if (resultContainerMatch && resultContainerMatch[1]) {
            try {
                const jsonData = JSON.parse(resultContainerMatch[1]);
                console.log('✅ Successfully extracted complete JSON from resultContainer');
                return extractDataFromJson(jsonData);
            } catch (error) {
                console.log('⚠️ resultContainer JSON parse failed, continuing with regex extraction...');
            }
        }
        
        // Check if we got a different response format (script/gtm content)
        // But allow valid responses that contain resultContainer even with GTM scripts
        if ((responseData.includes('window.gtminfo') || responseData.includes('google_tag_manager')) &&
            !responseData.includes('<div id="resultContainer">') &&
            !responseData.includes('"slugKuratorGroup"')) {
            console.log('❌ Received tracking/analytics content instead of game data');
            return {
                success: false,
                error: 'Response contains tracking content instead of game data - API returned wrong format',
                metadata: null,
                games: [],
                remainingGames: 0
            };
        }
        
        // Check for simple "error" response
        if (responseData.trim() === 'error' || responseData.length < 100) {
            console.log('❌ Received simple error response');
            return {
                success: false,
                error: 'API returned simple error response',
                metadata: null,
                games: [],
                remainingGames: 0
            };
        }
        
        // Extract provider metadata using improved regex
        const providerMatch = responseData.match(/"slugKuratorGroup":\s*\{\s*"id":\s*"([^"]+)"\s*,\s*"slug":\s*"([^"]+)"\s*,\s*"translation":\s*"([^"]+)"[^}]*?"gameCount":\s*(\d+)/);
        if (!providerMatch) {
            throw new Error('Could not find provider metadata');
        }
        
        const metadata = {
            providerId: providerMatch[1],
            providerSlug: providerMatch[2],
            providerName: providerMatch[3].replace(/\\"/g, '"'), // Unescape quotes
            providerIcon: '',
            providerType: 'provider',
            totalGameCount: parseInt(providerMatch[4]),
            fetchedGamesCount: 0
        };
        
        // Extract individual games using improved regex
        const games = [];
        
        // Enhanced game pattern to catch more variations
        const gamePattern = /"game":\s*\{\s*[^}]*?"id":\s*"([^"]+)"[^}]*?"name":\s*"([^"]+)"[^}]*?"slug":\s*"([^"]+)"[^}]*?"thumbnailUrl":\s*"([^"]*)"[^}]*?"thumbnailBlurHash":\s*"([^"]*)"[^}]*?"isBlocked":\s*(true|false)[^}]*?"isWidgetEnabled":\s*(true|false)[^}]*?(?:"playerCount":\s*(\d+))?/g;
        
        let gameMatch;
        let gameIndex = 0;
        
        while ((gameMatch = gamePattern.exec(responseData)) !== null && gameIndex < 50) { // Limit for safety
            const game = {
                id: gameMatch[1],
                name: gameMatch[2].replace(/\\"/g, '"').replace(/&amp;/g, '&'), // Unescape quotes and HTML entities
                slug: gameMatch[3],
                thumbnailUrl: gameMatch[4],
                thumbnailBlurHash: gameMatch[5] || null,
                isBlocked: gameMatch[6] === 'true',
                isWidgetEnabled: gameMatch[7] === 'true',
                playerCount: gameMatch[8] ? parseInt(gameMatch[8]) : 0,
                groupGames: [] // Will be populated separately if needed
            };
            
            games.push(game);
            gameIndex++;
        }
        
        metadata.fetchedGamesCount = games.length;
        
        if (games.length === 0) {
            console.log('⚠️ No games found with regex parsing');
            // Try alternative extraction
            return parseAlternativeFormat(responseData);
        }
        
        console.log(`📊 Parsed ${games.length} games from ${metadata.providerName} using regex`);
        console.log(`📊 Total games available: ${metadata.totalGameCount}`);
        
        return {
            success: true,
            metadata,
            games,
            remainingGames: Math.max(0, metadata.totalGameCount - games.length)
        };
        
    } catch (error) {
        console.error('❌ Regex parse error:', error.message);
        return {
            success: false,
            error: error.message,
            metadata: null,
            games: [],
            remainingGames: 0
        };
    }
}

/**
 * Parse alternative response formats (fallback method)
 * @param {string} responseData - Response data
 * @returns {Object} Parsed data
 */
function parseAlternativeFormat(responseData) {
    try {
        console.log('🔄 Attempting alternative format parsing...');
        
        // Look for any JSON-like structure
        const jsonMatches = responseData.match(/\{[^{}]*"data"[^{}]*\{[^{}]*"slugKuratorGroup"[^{}]*\}/g);
        if (jsonMatches && jsonMatches.length > 0) {
            for (const jsonMatch of jsonMatches) {
                try {
                    const parsed = JSON.parse(jsonMatch);
                    if (parsed.data && parsed.data.slugKuratorGroup) {
                        console.log('✅ Found valid data in alternative format');
                        return extractDataFromJson(parsed);
                    }
                } catch (e) {
                    continue;
                }
            }
        }
        
        throw new Error('No valid game data found in alternative formats');
        
    } catch (error) {
        console.error('❌ Alternative format parse error:', error.message);
        return {
            success: false,
            error: `Alternative parsing failed: ${error.message}`,
            metadata: null,
            games: [],
            remainingGames: 0
        };
    }
}

/**
 * Extract data from parsed JSON object
 * @param {Object} jsonData - Parsed JSON
 * @returns {Object} Parsed data
 */
function extractDataFromJson(jsonData) {
    // Extract provider data
    const providerData = jsonData.data?.slugKuratorGroup;
    if (!providerData) {
        throw new Error('No slugKuratorGroup data found in response');
    }
    
    // Parse games list
    const games = [];
    const gamesList = providerData.groupGamesList || [];
    
    gamesList.forEach(gameItem => {
        const game = gameItem.game;
        if (game) {
            const parsedGame = {
                id: game.id,
                name: game.name,
                slug: game.slug,
                thumbnailUrl: game.thumbnailUrl,
                thumbnailBlurHash: game.thumbnailBlurHash,
                isBlocked: game.isBlocked,
                isWidgetEnabled: game.isWidgetEnabled,
                playerCount: game.playerCount || 0,
                groupGames: (game.groupGames || []).map(gg => ({
                    groupId: gg.group?.id,
                    groupSlug: gg.group?.slug,
                    groupTranslation: gg.group?.translation,
                    groupType: gg.group?.type
                }))
            };
            games.push(parsedGame);
        }
    });
    
    // Extract metadata
    const metadata = {
        providerId: providerData.id,
        providerSlug: providerData.slug,
        providerName: providerData.translation,
        providerIcon: providerData.icon,
        providerType: providerData.type,
        totalGameCount: providerData.gameCount,
        fetchedGamesCount: games.length
    };
    
    console.log(`📊 Parsed ${games.length} games from ${metadata.providerName}`);
    console.log(`📊 Total games available: ${metadata.totalGameCount}`);
    
    return {
        success: true,
        metadata,
        games,
        remainingGames: Math.max(0, metadata.totalGameCount - games.length)
    };
}

/**
 * Parse response from file
 * @param {string} filePath - Path to response file
 * @returns {Object} Parsed data
 */
function parseResponseFile(filePath) {
    try {
        const responseData = fs.readFileSync(filePath, 'utf8');
        console.log(`📁 Reading response file: ${filePath}`);
        return parseStakeResponse(responseData);
    } catch (error) {
        console.error('❌ File read error:', error.message);
        return {
            success: false,
            error: `File read error: ${error.message}`,
            metadata: null,
            games: [],
            remainingGames: 0
        };
    }
}

/**
 * Save parsed data to file
 * @param {Object} parsedData - Data from parseStakeResponse
 * @param {string} outputPath - Output file path
 */
function saveParsedData(parsedData, outputPath) {
    try {
        const outputData = {
            timestamp: new Date().toISOString(),
            ...parsedData
        };
        
        fs.writeFileSync(outputPath, JSON.stringify(outputData, null, 2));
        console.log(`💾 Parsed data saved to: ${outputPath}`);
        return true;
    } catch (error) {
        console.error('❌ Save error:', error.message);
        return false;
    }
}

// Example usage if run directly
if (require.main === module) {
    const args = process.argv.slice(2);
    const inputFile = args[0];
    const outputFile = args[1] || 'parsed_output.json';
    
    if (!inputFile) {
        console.log('Usage: node data_parser.js <input_file> [output_file]');
        console.log('Example: node data_parser.js stake_raw_response.txt parsed_games.json');
        process.exit(1);
    }
    
    if (!fs.existsSync(inputFile)) {
        console.error(`❌ Input file not found: ${inputFile}`);
        process.exit(1);
    }
    
    console.log('🔧 Starting data parsing...');
    const result = parseResponseFile(inputFile);
    
    if (result.success) {
        saveParsedData(result, outputFile);
        console.log('✅ Parsing completed successfully');
        console.log(`📊 Summary: ${result.games.length} games parsed from ${result.metadata.providerName}`);
        console.log(`📊 Remaining: ${result.remainingGames} games`);
    } else {
        console.error('❌ Parsing failed:', result.error);
        process.exit(1);
    }
}

module.exports = {
    parseStakeResponse,
    parseResponseFile,
    saveParsedData
};
